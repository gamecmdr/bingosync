from django import forms
from django.db import transaction
from django.contrib.auth import hashers

from .models import Room, Game, Player
from .bingo_generator import BingoGenerator


def make_read_only_char_field(*args, **kwargs):
    kwargs["widget"] = forms.TextInput(attrs={"readonly": "readonly"})
    return forms.CharField(*args, **kwargs)

ROOM_NAME_MAX_LENGTH = Room._meta.get_field("name").max_length
PLAYER_NAME_MAX_LENGTH = Player._meta.get_field("name").max_length

class RoomForm(forms.Form):
    room_name = forms.CharField(label="Room Name", max_length=ROOM_NAME_MAX_LENGTH)
    passphrase = forms.CharField(label="Passphrase", widget=forms.PasswordInput())
    nickname = forms.CharField(label="Nickname", max_length=PLAYER_NAME_MAX_LENGTH)
    seed = forms.CharField(label="Seed", widget=forms.NumberInput())

    def create_room(self):
        room_name = self.cleaned_data["room_name"]
        passphrase = self.cleaned_data["passphrase"]
        nickname = self.cleaned_data["nickname"]
        seed = self.cleaned_data["seed"]

        encrypted_passphrase = hashers.make_password(passphrase)
        with transaction.atomic():
            board_json = BingoGenerator.instance().get_card(seed)
            room = Room(name=room_name, passphrase=encrypted_passphrase)
            room.save()
            game = Game.from_board(board_json, room=room, seed=seed)
        return room

class JoinRoomForm(forms.Form):
    encoded_room_uuid = forms.CharField(label="Room UUID", max_length=128, widget=forms.HiddenInput())
    room_name = make_read_only_char_field(label="Room Name", max_length=ROOM_NAME_MAX_LENGTH)
    creator_name = make_read_only_char_field(label="Creator", max_length=PLAYER_NAME_MAX_LENGTH)
    player_name = forms.CharField(label="Nickname", max_length=PLAYER_NAME_MAX_LENGTH)
    passphrase = forms.CharField(label="Passphrase", widget=forms.PasswordInput())

    @staticmethod
    def for_room(room):
        initial_values = {
            "encoded_room_uuid": room.encoded_uuid,
            "room_name": room.name,
            "creator_name": "Placeholder"
        }
        return JoinRoomForm(initial=initial_values)

    def get_room(self):
        encoded_room_uuid = self.cleaned_data["encoded_room_uuid"]
        return Room.get_for_encoded_uuid(encoded_room_uuid)

    def clean(self):
        cleaned_data = super(JoinRoomForm, self).clean()
        encoded_room_uuid = cleaned_data.get("encoded_room_uuid")
        passphrase = cleaned_data.get("passphrase")

        if encoded_room_uuid and passphrase:
            room = Room.get_for_encoded_uuid(encoded_room_uuid)
            if not hashers.check_password(passphrase, room.passphrase):
                raise forms.ValidationError("Incorrect Passphrase")