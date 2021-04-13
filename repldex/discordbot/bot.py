import traceback
import discord
import base64
import os
import io
intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

from repldex.config import BLACKLISTED_IDS, CONFIG
from repldex import utils


class BetterBot:

	def __init__(self, prefix, bot_id):
		'''
		All the bot prefixes.
		Also allows pings
		'''
		self.prefixes = [
			prefix,
			f'<@{bot_id}>',
			f'<@!{bot_id}>'
		]
		self.commands = []

	async def try_converter(self, ctx, string, converter):
		if hasattr(converter, 'convert'):
			return await converter.convert(converter, ctx, string)
		try:
			return converter(string)
		except ValueError:
			return

	async def parse_args(self, parsing_remaining, func, ctx, ignore_extra=True):
		'''
		Parses the command arguments
		'''
		# Annotations are the expected types (str, int, Member, etc)
		ann = func.__annotations__
		# Args is all the arguments for the function
		args = func.__code__.co_varnames[1:]  # [1:] to skip ctx
		return_args = []
		for argnum, arg in enumerate(args):
			if arg in ann:
				hint = ann[arg]
				found = None
				i = 0
				for i in reversed([pos for pos, char in enumerate(parsing_remaining + ' ') if char == ' ']):
					cmd_arg = parsing_remaining[:i]
					tried = await self.try_converter(ctx, cmd_arg, hint)
					if tried is not None:
						found = tried
						break
				if found:
					parsing_remaining = parsing_remaining[i + 1:]
					if isinstance(found, str):
						found = found.strip()
					return_args.append(found)
				else:
					parsing_remaining = (parsing_remaining + ' ').split(' ', len(args) - argnum)[-1]
					return_args.append(None)
			else:
				cmd_arg, parsing_remaining = (parsing_remaining + ' ').split(' ', 1)
				if cmd_arg:
					if isinstance(cmd_arg, str):
						cmd_arg = cmd_arg.strip()
					return_args.append(cmd_arg)
		if parsing_remaining.strip():
			if not ignore_extra:
				raise Exception('Extra data left')
		return return_args

	async def process_commands(self, message):
		parsing_remaining = message.content.replace('  ', ' ')
		found_prefix = False
		prefix = None
		for prefix in self.prefixes:
			if parsing_remaining.startswith(prefix):
				found_prefix = True
				break
		if not found_prefix:
			# no prefix found in the message
			return
		parsing_remaining = parsing_remaining[len(prefix):].strip()
		command_name, parsing_remaining = (parsing_remaining + ' ').split(' ', 1)
		command_name = command_name.lower()
		for command in self.commands:
			if command_name != command['name']:
				continue
			func = command['function']
			pad_none = command['pad_none']
			bots_allowed = command['bots_allowed']
			always_allowed = command['always_allowed']

			if message.author.bot and not bots_allowed:
				# if bots aren't allowed and the author's a bot, kill it. discrimination pog!
				return

			if message.author.id in BLACKLISTED_IDS and not always_allowed:
				# if the author is blacklisted and the command isn't always allowed, kill them
				return

			ctx = Context(message, client, prefix=prefix)
			if parsing_remaining:
				try:
					return_args = await self.parse_args(parsing_remaining, func, ctx, ignore_extra=pad_none)
				except Exception as e:
					traceback.print_exc()
					print('error parsing?', type(e), e, func.__code__.co_filename)
					continue
			else:
				return_args = []
			for attempt in range(10):
				try:
					return await func(ctx, *return_args)
				except TypeError:
					if pad_none:
						return_args.append(None)
					else:
						break
				except BaseException as e:
					print('error :(')
					traceback.print_exc()
					return

	def command(self, name, aliases=[], allowed=False, bots_allowed=False):
		def decorator(func):
			for command_name in [name] + aliases:
				self.commands.append(
					# TODO: make this a class instead of dict maybe idk
					{
						'name': command_name.lower(),
						'function': func,
						'pad_none': True,
						'always_allowed': allowed,
						'bots_allowed': bots_allowed
					}
				)
			return func
		return decorator


class Context:  # very unfinished but its fine probably
	__slots__ = ('message', 'channel', 'guild', 'author', 'prefix', 'client')

	async def send(self, *args, embed=None, **kwargs):
		message = await self.message.channel.send(*args, **kwargs, embed=embed)
		if embed:
			try:
				await message.add_reaction(utils.x_emoji)
			except discord.errors.Forbidden:
				pass
			utils.commands_ran_by[message.id] = self.author.id
			for _ in range(10):
				await self.client.wait_for('message', check=lambda m: m.channel == message.channel)
			await message.delete()
		return message

	def __init__(self, message, client, prefix=None):
		self.message = message
		self.channel = message.channel
		self.guild = message.guild
		self.author = message.author

		self.prefix = prefix
		self.client = client


class NothingFound(BaseException):
	pass


bot_token = os.getenv('token')

if bot_token:
	# first part of the token is always the bot id
	bot_id = int(base64.b64decode(bot_token.split('.')[0]))
else:
	bot_id = 0  # might be set later by a unit test, so just default to 0


async def start_bot():
	if not bot_token:
		raise Exception('No token found')
	print('starting bot pog')
	await client.start(bot_token)


async def log_edit(editor, title, time):
	channel = client.get_channel(770468229410979881)
	await channel.send(f'{time}: <@{editor}>({editor}) edited {title}')


async def log_delete(entry_data, time_):
	# make sure content is string
	channel = client.get_channel(770468181486600253)
	title = entry_data.get('title')
	await channel.send(f'{title} has been deleted (through Repldex [direct database deletions are not detected]) at {time_}')
	await channel.send(file=discord.File(fp=io.BytesIO(entry_data['content'].encode('utf8')),filename=title+'.html'))
	if entry_data.get('image', False):
		await channel.send(content=entry_data.get('image')['src'])

async def log_view(title, time):
	channel = client.get_channel(770468271195553823)
	await channel.send(f'{title} has been viewed at {time}')


# duplicate?
# async def log_view(title, time, newurl):
# 	channel = client.get_channel(770498997428551680)
# 	await channel.send(title+" has been unlisted at "+time+" new url is "+newurl)

prefix = CONFIG.get('prefix', '^')


@client.event
async def on_ready():
	print('ready')
	await client.change_presence(activity=discord.Game(name=prefix + 'help'))


def discord_id_to_user(user_id):
	user = client.get_user(user_id)
	return str(user) if user else None


betterbot = BetterBot(prefix=prefix, bot_id=bot_id)


@client.event
async def on_message(message):
	await betterbot.process_commands(message)


@client.event
async def on_raw_reaction_add(payload):
	message_id = payload.message_id
	if message_id not in utils.commands_ran_by:
		return
	channel_id = payload.channel_id
	channel = client.get_channel(channel_id)
	message = await channel.fetch_message(message_id)

	author = utils.commands_ran_by[message.id]

	x_reactions = 0
	author_reacted = False
	for reaction in message.reactions:
		if reaction.emoji == utils.x_emoji:
			async for user in reaction.users():
				if user.id != client.user.id:
					x_reactions += 1
				if user.id == author:
					author_reacted = True
		if x_reactions >= 3 or author_reacted:
			try:
				await message.delete()
			except discord.errors.NotFound:
				pass


# this is required to make bot commands work, must be at the end otherwise it causes a circular import
from . import commands  # noqa: F401,E261
