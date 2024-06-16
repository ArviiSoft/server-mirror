from os import system
mytitle = "ArviS Server Copier"
system("title "+mytitle)
import psutil
import time
import sys
import discord
import asyncio
import colorama
from colorama import Fore, init, Style
import platform
from serverclone import Clone

client = discord.Client(intents=discord.Intents.default())

os = platform.system()
if os == "Windows":
    system("cls")
else:
    system("clear")
    print(chr(27) + "[2J")
print(f"""{Fore.RED}
 ░▒▓██████▓▒░ ░▒▓███████▓▒░ ░▒▓█▓▒░░▒▓█▓▒ ░▒▓█▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░░▒▓█▓▒ ░▒▓█▓▒░░▒▓█▓▒ ░▒▓█▓▒░░▒▓█▓▒ ░▒▓█▓▒░ ▒▓█▓▒░        
░▒▓█▓▒░░▒▓█▓▒ ░▒▓█▓▒░░▒▓█▓▒ ░░▒▓█▓▒▒▓█▓▒░ ░▒▓█▓▒░ ▒▓█▓▒░        
░▒▓████████▓▒ ░▒▓███████▓▒░  ░▒▓█▓▒▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓██████▓▒░  
░▒▓█▓▒░░▒▓█▓▒ ░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▓█▓▒░  ░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░░▒▓█▓▒ ░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▓█▓▒░  ░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░░▒▓█▓▒ ░▒▓█▓▒░░▒▓█▓▒░   ░▒▓██▓▒░   ░▒▓█▓▒░ ▒▓███████▓▒░                                                                                                            
{Style.RESET_ALL}""")

token = input(f'? Hesap Tokenini Gir (Token Saklanmaz/Kaydedilmez)\n ->')

guild_s = input('\n Kopyalanacak Sunucu ID`si\n ->')

guild = input('\n Kopyaların Aktarılacağı Sunucu ID`si\n ->')

input_guild_id = guild_s 
output_guild_id = guild 
token = token  

print("  ")
print("  ")

@client.event
async def on_ready():
    extrem_map = {}
    print(f"""{Fore.GREEN}[GİRİŞ YAPILDI]""" f"""{Fore.WHITE}{client.user}""")
    print(f"""{Fore.GREEN}Sunucu Kopyalanıyor\n\n""")
    guild_from = client.get_guild(int(input_guild_id))
    guild_to = client.get_guild(int(output_guild_id))
    await Clone.guild_edit(guild_to, guild_from)
    await Clone.roles_delete(guild_to)
    await Clone.channels_delete(guild_to)
    await Clone.roles_create(guild_to, guild_from)
    await Clone.categories_create(guild_to, guild_from)
    await Clone.channels_create(guild_to, guild_from)
    print(f"""{Fore.GREEN}
  _  ______  _______     __      _               _   _ _____ _____ 
 | |/ / __ \|  __ \ \   / //\   | |        /\   | \ | |  __ \_   _|
 | ' / |  | | |__) \ \_/ //  \  | |       /  \  |  \| | |  | || |  
 |  <| |  | |  ___/ \   // /\ \ | |      / /\ \ | . ` | |  | || |  
 | . \ |__| | |      | |/ ____ \| |____ / ____ \| |\  | |__| || |_ 
 |_|\_\____/|_|      |_/_/    \_\______/_/    \_\_| \_|_____/_____|                                                                                                                    
    {Style.RESET_ALL}""")
    await asyncio.sleep(5)
    await client.close()


client.run(token, bot=False)
