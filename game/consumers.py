from channels.generic.websocket import AsyncWebsocketConsumer
import json
from .helpers import checkWin, isDraw

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
                'current_turn': 'X'
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
            if self.channel_name in self.rooms[self.room_id]['players']:
                self.rooms[self.room_id]['players'].remove(self.channel_name)
                # Reset room state
                self.rooms[self.room_id]['board'] = {str(i): '' for i in range(9)}
                self.rooms[self.room_id]['current_turn'] = 'X'
                # Notify other player
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'opponent_left',
                    }
                )

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        room = self.rooms[self.room_id]

        if data['event'] == 'boardData_send':
            room['board'] = data['board']
            winner = checkWin(room['board'])
            
            if winner:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'game_won',
                        'winner': winner,
                        'board': room['board']
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
            'myTurn': is_first_player
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
            'board': event['board']
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


