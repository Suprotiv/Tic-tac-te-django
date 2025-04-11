from channels.generic.websocket import AsyncWebsocketConsumer
import json
from .helpers import checkWin, isDraw
from asgiref.sync import sync_to_async
from game.models import Room 

class GameConsumer(AsyncWebsocketConsumer):
    rooms = {}  # Store room state

    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['id']
        self.room_group_name = f'game_{self.room_id}'

        # Initialize room if doesn't exist
        if self.room_id not in self.rooms:
            self.rooms[self.room_id] = {
        'players': [],
        'board': {str(i): '' for i in range(9)},
        'current_turn': 'X',
        'scores': {
            'X': 0,
            'O': 0
        }
        }


        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # Add player to room
        if len(self.rooms[self.room_id]['players']) < 2:
            self.rooms[self.room_id]['players'].append(self.channel_name)
            if len(self.rooms[self.room_id]['players']) == 2:
                # Start game when second player joins
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'game_start',
                        'board': self.rooms[self.room_id]['board']
                    }
                )
        else:
            await self.send(json.dumps({
                'event': 'show_error',
                'error': 'Room is full'
            }))
            await self.close()

    async def disconnect(self, close_code):
        if self.room_id in self.rooms:
            players = self.rooms[self.room_id]['players']
            if self.channel_name in players:
                players.remove(self.channel_name)

                # Notify remaining player, if any
                if players:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'opponent_left',
                        }
                    )

            # If no players left, clean up
            if not players:
                del self.rooms[self.room_id]
                await self.delete_room_from_db()

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    @sync_to_async
    def delete_room_from_db(self):
        try:
            Room.objects.get(id=self.room_id).delete()
        except Room.DoesNotExist:
            pass



    async def receive(self, text_data):
        data = json.loads(text_data)
        room = self.rooms[self.room_id]

        if data['event'] == 'boardData_send':
            room['board'] = data['board']
            winner = checkWin(room['board'])
            
            if winner:
                self.rooms[self.room_id]['scores'][winner] += 1
                await self.channel_layer.group_send(
                self.room_group_name,
                    {
                        'type': 'game_won',
                        'winner': winner,
                        'board': room['board'],
                        'scores': self.rooms[self.room_id]['scores']
                    }
    )

            elif isDraw(room['board']):
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'game_draw',
                        'board': room['board']
                    }
                )
            else:
                room['current_turn'] = 'O' if room['current_turn'] == 'X' else 'X'
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'board_update',
                        'board': room['board']
                    }
                )
        
        elif data['event'] == 'restart':
            room['board'] = {str(i): '' for i in range(9)}
            room['current_turn'] = 'X'
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_start',
                    'board': room['board']
                }
            )

    async def game_start(self, event):
        is_first_player = self.channel_name == self.rooms[self.room_id]['players'][0]
        await self.send(json.dumps({
            'event': 'game_start',
            'board': event['board'],
            'myTurn': is_first_player,
            'scores': self.rooms[self.room_id]['scores']
        }))

    async def board_update(self, event):
        is_my_turn = (self.rooms[self.room_id]['current_turn'] == 'X' and 
                     self.channel_name == self.rooms[self.room_id]['players'][0]) or \
                    (self.rooms[self.room_id]['current_turn'] == 'O' and 
                     self.channel_name == self.rooms[self.room_id]['players'][1])
        await self.send(json.dumps({
            'event': 'boardData_send',
            'board': event['board'],
            'myTurn': is_my_turn
        }))

    async def game_won(self, event):
        await self.send(json.dumps({
            'event': 'won',
            'winner': event['winner'],
            'board': event['board'],
            'scores': event['scores']
        }))


    async def game_draw(self, event):
        await self.send(json.dumps({
            'event': 'draw',
            'board': event['board']
        }))

    async def opponent_left(self, event):
        await self.send(json.dumps({
            'event': 'opponent_left',
            'board': self.rooms[self.room_id]['board']
        }))


