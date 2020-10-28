from betterbot import BetterBot
import discord
import base64
import utils
import json
import os


intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)


with open('config/config.json', 'r') as f:
	config = json.loads(f.read())

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


async def log_delete(title, time):
	channel = client.get_channel(770468181486600253)
	await channel.send(f'{title} has been deleted at {time}')


async def log_view(title, time):
	channel = client.get_channel(770468271195553823)
	await channel.send(f'{title} has been viewed at {time}')


# duplicate?
# async def log_view(title, time, newurl):
# 	channel = client.get_channel(770498997428551680)
# 	await channel.send(title+" has been unlisted at "+time+" new url is "+newurl)


@client.event
async def on_ready():
	print('ready')
	await client.change_presence(
		activity=discord.Game(name='^help')
	)


def discord_id_to_user(user_id):
	user = client.get_user(user_id)
	return str(user)


prefix = config.get('prefix', '^')

betterbot = BetterBot(
	prefix=prefix,
	bot_id=bot_id
)


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
