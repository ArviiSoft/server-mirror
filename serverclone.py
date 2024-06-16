import discord
from colorama import Fore, init, Style


def print_add(message):
    print(f'{Fore.GREEN}[+]{Style.RESET_ALL} {message}')

def print_delete(message):
    print(f'{Fore.RED}[-]{Style.RESET_ALL} {message}')

def print_warning(message):
    print(f'{Fore.RED}[DİKKAT]{Style.RESET_ALL} {message}')


def print_error(message):
    print(f'{Fore.RED}[HATA]{Style.RESET_ALL} {message}')


class Clone:
    @staticmethod
    async def roles_delete(guild_to: discord.Guild):
            for role in guild_to.roles:
                try:
                    if role.name != "@everyone":
                        await role.delete()
                        print_delete(f"Rol SİLİNDİ: ( {role.name} )")
                except discord.Forbidden:
                    print_error(f"Rol Silinirken HATA Oluştu: ( {role.name} )")
                except discord.HTTPException:
                    print_error(f"Rol SİLİNEMİYOR: ( {role.name} )")

    @staticmethod
    async def roles_create(guild_to: discord.Guild, guild_from: discord.Guild):
        roles = []
        role: discord.Role
        for role in guild_from.roles:
            if role.name != "@everyone":
                roles.append(role)
        roles = roles[::-1]
        for role in roles:
            try:
                await guild_to.create_role(
                    name=role.name,
                    permissions=role.permissions,
                    colour=role.colour,
                    hoist=role.hoist,
                    mentionable=role.mentionable
                )
                print_add(f"Rol OLUŞTURULDU: ( {role.name} )")
            except discord.Forbidden:
                print_error(f"Rol Oluşturulurken HATA Oluştu: ( {role.name} )")
            except discord.HTTPException:
                print_error(f"Rol OLUŞTURULAMIYOR: ( {role.name} )")

    @staticmethod
    async def channels_delete(guild_to: discord.Guild):
        for channel in guild_to.channels:
            try:
                await channel.delete()
                print_delete(f"Kanal SİLİNDİ: ( {channel.name} )")
            except discord.Forbidden:
                print_error(f"Kanal Silinirken HATA Oluştu: ( {channel.name} )")
            except discord.HTTPException:
                print_error(f"Kanal OLUŞTURULAMIYOR: ( {channel.name} )")

    @staticmethod
    async def categories_create(guild_to: discord.Guild, guild_from: discord.Guild):
        channels = guild_from.categories
        channel: discord.CategoryChannel
        new_channel: discord.CategoryChannel
        for channel in channels:
            try:
                overwrites_to = {}
                for key, value in channel.overwrites.items():
                    role = discord.utils.get(guild_to.roles, name=key.name)
                    overwrites_to[role] = value
                new_channel = await guild_to.create_category(
                    name=channel.name,
                    overwrites=overwrites_to)
                await new_channel.edit(position=channel.position)
                print_add(f"Kategori OLUŞTURULDU: ( {channel.name} )")
            except discord.Forbidden:
                print_error(f"Kategori Oluşturulurken HATA Oluştu: ( {channel.name} )")
            except discord.HTTPException:
                print_error(f"Kategori OLUŞTURULAMIYOR: ( {channel.name} )")

    @staticmethod
    async def channels_create(guild_to: discord.Guild, guild_from: discord.Guild):
        channel_text: discord.TextChannel
        channel_voice: discord.VoiceChannel
        category = None
        for channel_text in guild_from.text_channels:
            try:
                for category in guild_to.categories:
                    try:
                        if category.name == channel_text.category.name:
                            break
                    except AttributeError:
                        print_warning(f" ( {channel_text.name} ) adlı YAZI kanalı her hangi bir kategoride değil!")
                        category = None
                        break

                overwrites_to = {}
                for key, value in channel_text.overwrites.items():
                    role = discord.utils.get(guild_to.roles, name=key.name)
                    overwrites_to[role] = value
                try:
                    new_channel = await guild_to.create_text_channel(
                        name=channel_text.name,
                        overwrites=overwrites_to,
                        position=channel_text.position,
                        topic=channel_text.topic,
                        slowmode_delay=channel_text.slowmode_delay,
                        nsfw=channel_text.nsfw)
                except:
                    new_channel = await guild_to.create_text_channel(
                        name=channel_text.name,
                        overwrites=overwrites_to,
                        position=channel_text.position)
                if category is not None:
                    await new_channel.edit(category=category)
                print_add(f"Yazı Kanalı OLUŞTURULDU: ( {channel_text.name} )")
            except discord.Forbidden:
                print_error(f"Yazı Kanalı Oluşturulurken HATA Oluştu: ( {channel_text.name} )")
            except discord.HTTPException:
                print_error(f"Yazı Kanalı OLUŞTURULAMIYOR: ( {channel_text.name} )")
            except:
                print_error(f"Yazı Kanalı Oluşturulurken HATA Oluştu: ( {channel_text.name} )")

        category = None
        for channel_voice in guild_from.voice_channels:
            try:
                for category in guild_to.categories:
                    try:
                        if category.name == channel_voice.category.name:
                            break
                    except AttributeError:
                        print_warning(f"( {channel_voice.name} ) adlı SES kanalı her hangi bir kategoride değil!")
                        category = None
                        break

                overwrites_to = {}
                for key, value in channel_voice.overwrites.items():
                    role = discord.utils.get(guild_to.roles, name=key.name)
                    overwrites_to[role] = value
                try:
                    new_channel = await guild_to.create_voice_channel(
                        name=channel_voice.name,
                        overwrites=overwrites_to,
                        position=channel_voice.position,
                        bitrate=channel_voice.bitrate,
                        user_limit=channel_voice.user_limit,
                        )
                except:
                    new_channel = await guild_to.create_voice_channel(
                        name=channel_voice.name,
                        overwrites=overwrites_to,
                        position=channel_voice.position)
                if category is not None:
                    await new_channel.edit(category=category)
                print_add(f"Ses Kanalı OLUŞTURULDU: ( {channel_voice.name} )")
            except discord.Forbidden:
                print_error(f"Ses Kanalı Oluşuturulurken HATA Oluştu: ( {channel_voice.name} )")
            except discord.HTTPException:
                print_error(f"Ses Kanalı OLUŞTURULAMIYOR: ( {channel_voice.name} )")
            except:
                print_error(f"Ses Kanalı Oluşuturulurken HATA Oluştu: ( {channel_voice.name} )")


    @staticmethod
    async def emojis_delete(guild_to: discord.Guild):
        for emoji in guild_to.emojis:
            try:
                await emoji.delete()
                print_delete(f"Emoji SİLİNDİ: ( {emoji.name} )")
            except discord.Forbidden:
                print_error(f"Emoji Silinirken HATA Oluştu: ( {emoji.name} )")
            except discord.HTTPException:
                print_error(f"Emoji Silinirken HATA Oluştu: ( {emoji.name} )")

    @staticmethod
    async def emojis_create(guild_to: discord.Guild, guild_from: discord.Guild):
        emoji: discord.Emoji
        for emoji in guild_from.emojis:
            try:
                emoji_image = await emoji.url.read()
                await guild_to.create_custom_emoji(
                    name=emoji.name,
                    image=emoji_image)
                print_add(f"Emoji OLUŞTURULDU: ( {emoji.name} )")
            except discord.Forbidden:
                print_error(f"Emoji Oluşturulurken HATA Oluştu: ( {emoji.name} )")
            except discord.HTTPException:
                print_error(f"Emoji Oluşturulurken HATA Oluştu: ( {emoji.name} )")

    @staticmethod
    async def guild_edit(guild_to: discord.Guild, guild_from: discord.Guild):
        try:
            try:
                icon_image = await guild_from.icon_url.read()
            except discord.errors.DiscordException:
                print_error(f"( {guild_from.name} ) adlı sunucunun profil resmi OKUNAMIYOR!")
                icon_image = None
            await guild_to.edit(name=f'{guild_from.name}')
            if icon_image is not None:
                try:
                    await guild_to.edit(icon=icon_image)
                    print_add(f"Sunucun Resmi DEĞİŞTİRİLDİ: ( {guild_to.name} )")
                except:
                    print_error(f"Sunucunun Resmi Değiştirilirken HATA Oluştu: ( {guild_to.name} )")
        except discord.Forbidden:
            print_error(f"Sunucunun Resmi Değiştirilirken HATA Oluştu: ( {guild_to.name} )")