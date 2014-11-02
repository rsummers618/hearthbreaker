import re
import json

import hearthbreaker
import hearthbreaker.constants
from hearthbreaker.constants import CHARACTER_CLASS
import hearthbreaker.game_objects
import hearthbreaker.cards
import hearthbreaker.game_objects
import hearthbreaker.proxies
from hearthbreaker.serialization.move import Move, AttackMove, PowerMove, TurnEndMove, \
    TurnStartMove, ConcedeMove, PlayMove
__doc__ = """
Responsible for reading and writing replays in either the compact or complete replay format (see the `replay format
<https://github.com/danielyule/hearthbreaker/blob/master/replay_format.md>`_ for details).

Recording a game
~~~~~~~~~~~~~~~~

Recording a game is a matter of creating a game, calling :meth:record on that game, playing the game, and then saving
the replay.  For example: ::

    game = create_a_game()                  # Create a game somehow
    replay = record(game)                   # Create a replay that will track the game's moves
    game.start()                            # Play the game
    replay.write_json("my_replay.hsreplay") # Save the replay to a file



Playing back a game
~~~~~~~~~~~~~~~~~~~

Playing back a game is a matter of loading the replay, getting a game for playing it back, and then starting the game
For example: ::

    replay = Replay()                      # create a new replay object
    replay.read_json("my_replay.hsreplay") # load the replay (this can be combined with the previous line)
    game = playback(replay)                # create a game associated with the replay
    game.start()                           # play the recorded game
"""


class Replay:
    """
    Encapsulates the data stored in a replay, along with functions to read and write replays.  The data
    stored in this class can be used for either recording or playing back replays.
    """
    def __init__(self, filename=None):
        """
        Create a new Replay.  This replay can be used for recording or playing back a game.

        If the `filename` string is present, then this will also load the file located at `filename` for playback

        :param string filename: A string representing a filename for a replay file to load or None (the default).
                                If present, it will load the selected replay and prepare it for playback.
                                The replay file must be in the complete format
        """
        self._moves = []
        self.__next_target = None
        self.decks = []
        self.keeps = []
        self.random = []
        if filename is not None:
            self.read_json(filename)

    def _save_decks(self, deck1, deck2):
        """
        Save the decks specified by the parameters

        :param hearthbreaker.game_objects.Deck deck1: The deck for player 1
        :param hearthbreaker.game_objects.Deck deck2: The deck for player 2
        """
        self.decks = [deck1, deck2]

    def _record_random(self, result):
        """
        Record a random number that has been generated by the system.

        This random number will be added to the header if the game hasn't started, or top the most recent
        move if it has.
        """
        if len(self._moves) > 0:
            self._moves[-1].random_numbers.append(result)
        else:
            self.random.append(result)

    def _record_card_played(self, card, index):
        """
        Record that a card has been played.  This will add a new PlayMove to the moves array
        """
        self._moves.append(PlayMove(hearthbreaker.proxies.ProxyCard(index), target=self.__next_target))
        self.__next_target = None

    def _record_option_chosen(self, option):
        """
        Record that an option was chosen.  This will update whichever is the most recent move
        """
        self.moves[-1].card.set_option(option)

    def _record_attack(self, attacker, target):
        """
        Record that an attack occurred.  This will create a new AttackMove in the moves array
        """
        self._moves.append(AttackMove(attacker, target))
        self.__next_target = None

    def _record_power(self):
        """
        Record that the current played used their hero power
        """
        self._moves.append(PowerMove(self.__next_target))
        self.__next_target = None

    def _record_target(self, target):
        """
        Record that a target was chosen.  This affects PlayMoves and PowerMoves.  AttackMoves have
        their target passed in as an argument
        """
        self.__next_target = target

    def _record_index(self, index):
        """
        Records the index that a minion is played at.  Will update the most recent move with this index
        """
        self._moves[-1].index = index

    def _record_kept_index(self, cards, card_index):
        """
        Records the index of the cards that a player kept.
        """
        k_arr = []
        for index in range(0, len(cards)):
            if card_index[index]:
                k_arr.append(index)
        self.keeps.append(k_arr)

    def __shorten_deck(self, cards):
        """
        Mostly for testing, this function will check if the deck is made up of a repeating pattern  and if so, shorten
        the output, since the parser will generate the pattern from a shorter sample
        :param cards: The deck of cards to replace
        :return: an array of cards that represents the deck if repeated until 30 cards are found
        """
        for pattern_length in range(1, 15):
            matched = True
            for index in range(pattern_length, 30):
                if not isinstance(cards[index % pattern_length], type(cards[index])):
                    matched = False
                    break
            if matched:
                return cards[0:pattern_length]

    def write(self, file):
        """
        Write a replay in the compact format.  This format is a series of directives, and isn't as flexible
        or well structured as the json format (in :meth:write_json).  For more info, see the
        `replay format <https://github.com/danielyule/hearthbreaker/blob/master/replay_format.md>`_

        :param file: Either a string or an IO object.  If a string, then it is assumed to be a filename describing
                     where a replay file is to be written.  If an IO object, then the IO object should be opened for
                     writing.
        :type file: :class:`str` or :class:`io.TextIOBase`
        """
        if 'write' not in dir(file):
            was_filename = True
            writer = open(file, 'w')
        else:
            was_filename = False
            writer = file

        for deck in self.decks:
            writer.write("deck(")
            writer.write(hearthbreaker.constants.CHARACTER_CLASS.to_str(deck.character_class))
            writer.write(",")
            writer.write(",".join([card.name for card in self.__shorten_deck(deck.cards)]))
            writer.write(")\n")
        found_random = False
        if self.random.count(0) == len(self.random):
            for move in self._moves:
                if move.random_numbers.count(0) != len(move.random_numbers):
                    found_random = True
                    break
        else:
            found_random = True
        if not found_random:
            writer.write("random()\n")
        else:
            writer.write("random(")
            writer.write(",".join([str(num) for num in self.random]))
            writer.write(")\n")

        for keep in self.keeps:
            writer.write("keep(")
            writer.write(",".join([str(k) for k in keep]))
            writer.write(")\n")

        for move in self._moves:
            writer.write(move.to_output_string() + "\n")
            if len(move.random_numbers) > 0:
                writer.write("random(")
                writer.write(",".join([str(num) for num in move.random_numbers]))
                writer.write(")\n")
        if was_filename:
            file.close()

    def write_json(self, file):
        """
        Write a replay in the complete json format.  This format is compatible with the netplay format, and is
        also designed to be more future proof.  For more info, see the
        `replay format <https://github.com/danielyule/hearthbreaker/blob/master/replay_format.md>`_

        :param file: Either a string or an IO object.  If a string, then it is assumed to be a filename describing
                     where a replay file should be written.  If an IO object, then the IO object should be opened for
                     writing.
        :type file: :class:`str` or :class:`io.TextIOBase`
        """
        was_filename = False
        if 'write' not in dir(file):
            was_filename = True
            writer = open(file, 'w')
        else:
            writer = file

        header_cards = [{"cards": [card.name for card in self.__shorten_deck(deck.cards)],
                         "class": CHARACTER_CLASS.to_str(deck.character_class)} for deck in self.decks]

        header = {
            'decks': header_cards,
            'keep': self.keeps,
            'random': self.random,
        }
        json.dump({'header': header, 'moves': self._moves}, writer, default=lambda o: o.__to_json__(), indent=2,
                  sort_keys=True)
        if was_filename:
            file.close()

    def read_json(self, file):
        """
        Read a replay in the complete json format.  This format is compatible with the netplay format, and is
        also designed to be more future proof.  For more info, see the
        `replay format <https://github.com/danielyule/hearthbreaker/blob/master/replay_format.md>`_

        :param file: Either a string or an IO object.  If a string, then it is assumed to be a filename describing
                     where a replay file is found.  If an IO object, then the IO object should be opened for
                     reading.
        :type file: :class:`str` or :class:`io.TextIOBase`
        """
        was_filename = False
        if 'read' not in dir(file):
            was_filename = True
            file = open(file, 'r')

        jd = json.load(file)
        self.decks = []
        for deck in jd['header']['decks']:
            deck_size = len(deck['cards'])
            cards = [hearthbreaker.game_objects.card_lookup(deck['cards'][index % deck_size]) for index in range(0, 30)]
            self.decks.append(
                hearthbreaker.game_objects.Deck(cards, CHARACTER_CLASS.from_str(deck['class'])))

        self.random = jd['header']['random']
        self.keeps = jd['header']['keep']
        if len(self.keeps) == 0:
            self.keeps = [[0, 1, 2], [0, 1, 2, 3]]
        self._moves = [Move.from_json(**js) for js in jd['moves']]
        if was_filename:
            file.close()

    def read(self, file):
        """
        Read a replay in the compact format.  This format is a series of directives, and isn't as flexible
        or well structured as the json format (in :meth:write_json).  For more info, see the
        `replay format <https://github.com/danielyule/hearthbreaker/blob/master/replay_format.md>`_

        :param file: Either a string or an IO object.  If a string, then it is assumed to be a filename describing
                     where a replay file is to be found.  If an IO object, then the IO object should be opened for
                     reading.
        :type file: :class:`str` or :class:`io.TextIOBase`
        """
        was_filename = False
        if 'read' not in dir(file):
            was_filename = True
            file = open(file, 'r')
        line_pattern = re.compile("\s*(\w*)\s*\(([^)]*)\)\s*(;.*)?$")
        for line in file:
            (move, args) = line_pattern.match(line).group(1, 2)
            args = [arg.strip() for arg in args.split(",")]
            if move == 'play':
                card = args[0]
                if len(args) > 1:
                    target = args[1]
                else:
                    target = None
                self._moves.append(PlayMove(hearthbreaker.proxies.ProxyCard(card), target=target))

            elif move == 'summon':
                card = args[0]

                index = int(args[1])

                if len(args) > 2:
                    target = args[2]
                else:
                    target = None

                self._moves.append(PlayMove(hearthbreaker.proxies.ProxyCard(card), index, target))
            elif move == 'attack':
                self._moves.append(AttackMove(args[0], args[1]))
            elif move == 'power':
                if len(args) > 0 and args[0] != '':
                    self._moves.append(PowerMove(args[0]))
                else:
                    self._moves.append(PowerMove())
            elif move == 'end':
                self._moves.append(TurnEndMove())
            elif move == 'start':
                self._moves.append(TurnStartMove())
            elif move == 'random':
                if len(self._moves) == 0:
                    if len(args[0]) > 0:
                        for num in args:
                            self.random.append(int(num))

                else:
                    for num in args:
                        if num.isdigit():
                            self._moves[-1].random_numbers.append(int(num))
                        else:
                            self._moves[-1].random_numbers.append(hearthbreaker.proxies.ProxyCharacter(num))

            elif move == 'deck':
                if len(self.decks) > 1:
                    raise Exception("Maximum of two decks per file")
                deck_size = len(args) - 1
                cards = [hearthbreaker.game_objects.card_lookup(args[1 + index % deck_size]) for index in range(0, 30)]
                self.decks.append(
                    hearthbreaker.game_objects.Deck(cards, hearthbreaker.constants.CHARACTER_CLASS.from_str(args[0])))

            elif move == 'keep':
                if len(self.keeps) > 1:
                    raise Exception("Maximum of two keep directives per file")
                self.keeps.append([int(a) for a in args])

            elif move == 'concede':
                self._moves.append(ConcedeMove())
        if was_filename:
            file.close()
        if len(self.keeps) is 0:
            self.keeps = [[0, 1, 2], [0, 1, 2, 3]]


def record(game):
    """
    Ready a game for recording.  This function must be called before the game is played.

    Several methods of the game and its agents are modified.  These modifications will not affect the operation
    of the game or its agents, although any further modifications to these methods will not be recorded.

    :param game: A game which has not been started
    :type game: :class:`Game <hearthbreaker.game_objects.Game>`
    :return: A replay that will track the actions of the game as it is played.  Once the game is complete,
                  this replay can be written to a file to remember the state of this game.
    :rtype: :class:`Replay`
    """
    class RecordingAgent:
        __slots__ = ['agent']

        def __init__(self, proxied_agent):
            object.__setattr__(self, "agent", proxied_agent)

        def choose_index(self, card, player):
            index = self.agent.choose_index(card, player)
            replay._record_index(index)
            return index

        def choose_target(self, targets):
            target = self.agent.choose_target(targets)
            replay._record_target(target)
            return target

        def choose_option(self, *options):
            option = self.agent.choose_option(options)

            replay._record_option_chosen(options.index(option))
            return option

        def __getattr__(self, item):
            return self.agent.__getattribute__(item)

        def __setattr__(self, key, value):
            setattr(self.__getattribute__("agent"), key, value)

    replay = hearthbreaker.replay.Replay()
    replay.random.append(game.first_player)

    game.players[0].agent = RecordingAgent(game.players[0].agent)
    game.players[1].agent = RecordingAgent(game.players[1].agent)

    if game.first_player == 0:
        replay._save_decks(game.players[0].deck, game.players[1].deck)
    else:
        replay._save_decks(game.players[1].deck, game.players[0].deck)

    game.bind("kept_cards", replay._record_kept_index)

    for player in game.players:
        player.bind("used_power", replay._record_power)
        player.hero.bind("found_power_target", replay._record_target)
        player.bind("card_played", replay._record_card_played)
        player.bind("attack", replay._record_attack)

    _old_random_choice = game.random_choice
    _old_generate_random_between = game._generate_random_between
    _old_start_turn = game._start_turn
    _old_end_turn = game._end_turn

    def random_choice(choice):
        result = _old_random_choice(choice)
        if isinstance(result, hearthbreaker.game_objects.Character):
            replay._moves[-1].random_numbers[-1] = hearthbreaker.proxies.ProxyCharacter(result)
        return result

    def _generate_random_between(lowest, highest):
        result = _old_generate_random_between(lowest, highest)
        replay._record_random(result)
        return result

    def _end_turn():
        replay._moves.append(TurnEndMove())
        _old_end_turn()

    def _start_turn():
        replay._moves.append(TurnStartMove())
        _old_start_turn()

    game.random_choice = random_choice
    game._generate_random_between = _generate_random_between
    game._end_turn = _end_turn
    game._start_turn = _start_turn

    return replay


def playback(replay):
    """
    Create a game which can be replayed back out of a replay.

    :param replay: The replay to load the game out of
    :type replay: :class:`Replay`
    :return: A game which when played will perform all of the actions in the replay.
    :rtype: :class:`Game <hearthbreaker.game_objects.Game>`
    """
    move_index = -1
    k_index = 0
    random_index = 0
    game = None

    class ReplayAgent:

        def __init__(self):
            self.next_target = None
            self.next_index = -1
            self.next_option = None

        def do_card_check(self, cards):
            nonlocal k_index
            keep_arr = [False] * len(cards)
            for index in replay.keeps[k_index]:
                keep_arr[int(index)] = True
            k_index += 1
            return keep_arr

        def do_turn(self, player):
            nonlocal move_index, random_index
            while move_index < len(replay._moves) and not player.hero.dead and type(
                    replay._moves[move_index]) is not hearthbreaker.serialization.move.TurnEndMove:
                random_index = 0
                replay._moves[move_index].play(game)
                move_index += 1

        def set_game(self, game):
            pass

        def choose_target(self, targets):
            return self.next_target

        def choose_index(self, card, player):
            return self.next_index

        def choose_option(self, *options):
            return options[self.next_option]
    game = hearthbreaker.game_objects.Game.__new__(hearthbreaker.game_objects.Game)
    _old_random_choice = game.random_choice
    _old_start_turn = game._start_turn
    _old_end_turn = game._end_turn
    _old_pre_game = game.pre_game

    def _generate_random_between(lowest, highest):
        nonlocal random_index
        if len(replay.random) == 0:
            return 0
        else:
            random_index += 1
            if move_index == -1:
                return replay.random[random_index - 1]
            return replay._moves[move_index].random_numbers[random_index - 1]

    def random_choice(choice):
        nonlocal move_index, random_index
        if isinstance(replay._moves[move_index].random_numbers[random_index], hearthbreaker.proxies.ProxyCharacter):
            result = replay._moves[move_index].random_numbers[random_index].resolve(game)
            random_index += 1
            return result
        return _old_random_choice(choice)

    def _start_turn():
        nonlocal move_index, random_index
        random_index = 0
        _old_start_turn()
        move_index += 1

    def _end_turn():
        nonlocal move_index, random_index
        random_index = 0
        _old_end_turn()
        move_index += 1

    def pre_game():
        nonlocal move_index
        _old_pre_game()
        move_index = 0

    game.random_choice = random_choice
    game._generate_random_between = _generate_random_between
    game._end_turn = _end_turn
    game._start_turn = _start_turn
    game.pre_game = pre_game

    game.__init__(replay.decks, [ReplayAgent(), ReplayAgent()])
    return game
