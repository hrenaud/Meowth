from meowth import Cog, command, bot
from discord.ext import commands
from meowth.utils.fuzzymatch import get_match, get_matches
from meowth.utils import formatters
import pywraps2 as s2
import aiohttp
import asyncio
import datetime
import time
import pytz
from pytz import timezone
import io
import codecs
from math import radians, degrees
import csv
from urllib.parse import quote_plus
import googlemaps

from .map_info import gmaps_api_key

gmaps = googlemaps.Client(key=gmaps_api_key)

class ReportChannel():
    def __init__(self, bot, channel):
        self.bot = bot
        self.channel = channel

    @property
    def _data(self):
        channel_query = self.bot.dbi.table('report_channels').query()
        _data = channel_query.where(channelid=self.channel.id)
        return _data
    
    async def center_coords(self):
        data = self._data
        record = (await data.get())[0]
        return (record['lat'], record['lon'])

    async def radius(self):
        data = self._data
        radius = await data.select('radius').get_value()
        return radius
    
    async def city(self):
        data = self._data
        city = await data.select('city').get_value()
        return city
    
    async def raid_report(self):
        data = self._data
        raid = await data.select('raid').get_value()
        return raid
    
    async def wild_report(self):
        data = self._data
        wild = await data.select('wild').get_value()
        return wild
    
    async def research_report(self):
        data = self._data
        research = await data.select('research').get_value()
        return research
    
    async def raidparty_report(self):
        data = self._data
        raidparty = await data.select('raidparty').get_value()
        return raidparty
    
    async def user_report(self):
        data = self._data
        user = await data.select('user').get_value()
        return user
    
    async def clean_mode(self):
        data = self._data
        clean = await data.select('clean').get_value()
        return clean
    
    async def s2_cap(self):
        coords = await self.center_coords()
        point = s2.S2LatLng.FromDegrees(*coords).ToPoint()
        radius = await self.radius()
        angle = radius/6371.0
        cap = s2.S2Cap(point, s2.S1Angle.Radians(angle))
        return cap

    async def point_in_channel(self, coords):
        cell = S2_L10.from_coords(self.bot, coords)
        covering = await self.level_10_covering()
        return cell.cellid in covering

    
    async def level_10_covering(self):
        cap = await self.s2_cap()
        coverer = s2.S2RegionCoverer()
        coverer.set_fixed_level(10)
        covering = coverer.GetCovering(cap)
        id_list = [hex(x.id()) for x in covering]
        return id_list

    async def get_all_gyms(self):
        covering = await self.level_10_covering()
        gyms = self.bot.dbi.table('gyms')
        gyms_query = gyms.query().where(gyms['l10'].in_(covering))
        gyms_query.where(guild=self.channel.guild.id)
        return gyms_query
    
    async def get_all_stops(self):
        covering = await self.level_10_covering()
        stops = self.bot.dbi.table('pokestops')
        stops_query = stops.query().where(stops['l10'].in_(covering))
        stops_query.where(guild=self.channel.guild.id)
        return stops_query
    


        


class S2_L10():

    def __init__(self, bot, cellid):
        self.bot = bot
        self.cellid = cellid
        
    @classmethod
    def from_coords(cls, bot, coords):
        cellid = hex(s2.S2CellId(
            s2.S2LatLng.FromDegrees(*coords)
        ).parent(10).id())
        return cls(bot, cellid)
    
    @property
    def center_coords(self):
        cellid = int(self.cellid, base=16)
        center_coords = s2.S2LatLng(s2.S2CellId(cellid).ToPoint())
        return center_coords
    
    async def weather_place(self):
        center_coords = self.center_coords
        url = 'http://dataservice.accuweather.com/locations/v1/geoposition/search.json'
        params = {
            'q': f"{center_coords.lat()},{center_coords.lng()}",
            'apikey': self.bot.config.weatherapikey,
            'toplevel': 'true'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                place_id = data[0]['Key']
                return place_id


    async def weather(self):
        weather_query = self.bot.dbi.table('weather_forecasts').query()
        current_hour = datetime.datetime.utcnow().hour % 12
        col = "current_weather"
        weather_query.select(col).where(cellid=self.cellid)
        weather = await weather_query.get_value()
        return weather
    
    async def correct_weather(self, weather):
        weather_table = self.bot.dbi.table('weather_forecasts')
        update = weather_table.update()
        update.where(cellid=self.cellid)
        current_hour = datetime.datetime.utcnow().hour % 12
        update.values(current_weather=weather)
        await update.commit()

    async def get_all_gyms(self):
        gyms_table = self.bot.dbi.table('gyms')
        gyms_query.select('id').where(l10=self.cellid)
        gyms = await gyms_query.get_values()
        return gyms



class POI():

    def __init__(self, bot, poi_id):
        self.bot = bot
        self.id = poi_id
    
    async def _coords(self):
        data = self._data
        record = (await data.get())[0]
        return (record['lat'], record['lon'])

    async def _L10(self):
        data = self._data
        L10 = await data.select('l10').get_value()
        return L10
    
    async def _name(self):
        data = self._data
        name = await data.select('name').get_value()
        return name
    
    async def _nick(self):
        data = self._data
        nick = await data.select('nickname').get_value()
        return nick
    
    async def _guildid(self):
        data = self._data
        guildid = await data.select('guild').get_value()
        return guildid
    
    async def guild(self):
        guildid = await self._guildid()
        guild = self.bot.get_guild(guildid)
        return guild
    
    async def url(self):
        lat, lon = await self._coords()
        prefix = "https://www.google.com/maps/dir/?api=1&"
        prefix += f"destination={lat},{lon}"
        prefix += "&dir_action=navigate"
        return prefix
    
    async def address(self):
        lat, lon = await self._coords()
        result = gmaps.reverse_geocode((lat, lon))
        if result:
            address = result[0].get('formatted_address', '')
        else:
            address = ''
        return address
    
    async def display_str(self):
        name = await self._name()
        address = await self.address()
        return f'{name} - {address}'
    
    async def weather(self):
        L10id = await self._L10()
        L10 = S2_L10(self.bot, L10id)
        weather = await L10.weather()
        return weather
    
    async def correct_weather(self, weather):
        L10id = await self._L10()
        L10 = S2_L10(self.bot, L10id)
        await L10.correct_weather(weather)
    
    async def get_all_channels(self, cmd):
        report_table = self.bot.dbi.table('report_channels')
        guild_id = await self._guildid()
        coords = await self._coords()
        query = report_table.query('channelid')
        query.where(guild_id=guild_id)
        if cmd == 'raid':
            query.where(raid=True)
        elif cmd == 'wild':
            query.where(wild=True)
        channelid_list = await query.get_values()
        channel_list = [ReportChannel(self.bot, self.bot.get_channel(x)) for x in channelid_list]
        gym_channels = [y for y in channel_list if await y.point_in_channel(coords)]
        return gym_channels
    
    @classmethod
    async def convert(cls, ctx, arg):
        # stop_convert = await Pokestop.convert(ctx, arg)
        # if isinstance(stop_convert, Pokestop):
        #     return stop_convert
        gym_convert = await Gym.convert(ctx, arg)
        return gym_convert

    

class Gym(POI):

    @property 
    def _data(self):
        data = self.bot.dbi.table('gyms').query()
        data = data.where(id=self.id)
        return data
    
    async def _exraid(self):
        data = self._data
        exraid = await data.select('exraid').get_value()
        return exraid

    @classmethod
    async def convert(cls, ctx, arg):
        report_channel = ReportChannel(ctx.bot, ctx.channel)
        gyms_query = await report_channel.get_all_gyms()
        gyms_query.select('id', 'name', 'nickname')
        data = await gyms_query.get()
        nick_dict = {}
        for x in data:
            if x.get('nickname'):
                nick_dict[x['nickname']] = x['id']
            else:
                continue
        name_dict = {x['name'] : x['id'] for x in data}
        if nick_dict:
            nick_matches = get_matches(nick_dict.keys(), arg)
            if nick_matches:
                nick_ids = [nick_dict[x[0]] for x in nick_matches]
            else:
                nick_ids = []
        else:
            nick_matches = []
            nick_ids = []
        name_matches = get_matches(name_dict.keys(), arg)
        if name_matches:
            name_ids = [name_dict[x[0]] for x in name_matches]
        else:
            name_ids = []
        possible_ids = set(nick_ids) | set(name_ids)
        id_list = list(possible_ids)
        if len(id_list) > 1:
            possible_gyms = [cls(ctx.bot, y) for y in id_list]
            names = [await z.display_str() for z in possible_gyms]
            react_list = formatters.mc_emoji(len(id_list))
            choice_dict = dict(zip(react_list, id_list))
            display_dict = dict(zip(react_list, names))
            embed = formatters.mc_embed(display_dict)
            multi = await chn.send('Multiple possible Gyms found! Please select from the following list.',
                embed=embed)
            payload = await formatters.ask(bot, [multi], user_list=[user_id],
                react_list=react_list)
            gym_id = choice_dict[str(payload.emoji)]
            await multi.delete()
        elif id_list == 1:
            gym_id = id_list[0]
        else:
            city = await report_channel.city()
            return PartialPOI(ctx.bot, city, arg)
        return cls(ctx.bot, gym_id)
    
    @classmethod
    async def insert_from_data(cls, bot, guildid, data):
        gyms_table = bot.dbi.table('gyms')
        insert = gyms_table.insert()
        data['guild'] = guildid
        insert.row(**data)
        rcrdlist = await insert.commit(do_update=True)
        rcrd = rcrdlist[0]
        return cls(bot, rcrd['id'])


class PartialPOI():

    def __init__(self, bot, city, arg):
        self.bot = bot
        self.city = city
        self.arg = arg

    @property
    def _name(self):
        return self.arg.title()
    
    @property
    def url(self):
        urlbase = 'https://www.google.com/maps/search/?api=1&query='
        urlsuff = self.arg + '+'
        urlsuff += self.city
        url = urlbase + quote_plus(urlsuff)
        return url

    async def weather(self):
        return "NO_WEATHER"



class Pokestop(POI):

    @property
    def _data(self):
        data = self.bot.dbi.table('stops').query()
        data = data.where(stop_id=self.id)
        return data

    @classmethod
    async def convert(cls, ctx, arg):
        report_channel = ReportChannel(ctx.bot, ctx.channel)
        stops_query = await report_channel.get_all_stops()
        stops_query.select('id', 'name', 'nickname')
        data = await stops_query.get()
        nick_dict = {}
        for x in data:
            if x.get('nickname'):
                nick_dict[x['nickname']] = x['id']
            else:
                continue
        name_dict = {x['name'] : x['id'] for x in data}
        if nick_dict:
            nick_matches = get_matches(nick_dict.keys(), arg)
            if nick_matches:
                nick_ids = [nick_dict[x[0]] for x in nick_matches]
            else:
                nick_ids = []
        else:
            nick_matches = []
            nick_ids = []
        name_matches = get_matches(name_dict.keys(), arg)
        if name_matches:
            name_ids = [name_dict[x[0]] for x in name_matches]
        else:
            name_ids = []
        possible_ids = set(nick_ids) | set(name_ids)
        id_list = list(possible_ids)
        if len(id_list) > 1:
            possible_stops = [cls(ctx.bot, y) for y in id_list]
            names = [await z.display_str() for z in possible_stops]
            react_list = formatters.mc_emoji(len(id_list))
            choice_dict = dict(zip(react_list, id_list))
            display_dict = dict(zip(react_list, names))
            embed = formatters.mc_embed(display_dict)
            multi = await chn.send('Multiple possible Pokestops found! Please select from the following list.',
                embed=embed)
            payload = await formatters.ask(bot, [multi], user_list=[user_id],
                react_list=react_list)
            stop_id = choice_dict[str(payload.emoji)]
            await multi.delete()
        elif id_list == 1:
            stop_id = id_list[0]
        else:
            city = await report_channel.city()
            return PartialPOI(ctx.bot, city, arg)
        return cls(ctx.bot, stop_id)


class Mapper(Cog):

    def __init__(self, bot):
        self.bot = bot
    
    async def gyms_from_csv(self, guildid, file):
        bot = self.bot
        gyms_table = bot.dbi.table('gyms')
        insert = gyms_table.insert()
        reader = csv.DictReader(codecs.iterdecode(file.readlines(), 'utf-8'))
        rows = []
        for row in reader:
            valid_data = {}
            valid_data['guild'] = guildid
            if isinstance(row.get('name'), str):
                valid_data['name'] = row['name']
            else:
                continue
            if isinstance(row.get('nickname'), str):
                valid_data['nickname'] = row.get('nickname')
            else:
                pass
            try:
                lat = float(row.get('lat'))
                lon = float(row.get('lon'))
            except:
                continue
            l10 = S2_L10.from_coords(bot, (lat, lon))
            valid_data['lat'] = lat
            valid_data['lon'] = lon
            valid_data['l10'] = l10.cellid
            if isinstance(row.get('exraid'), str):
                if row['exraid'].lower() == 'false':
                    valid_data['exraid'] = False
                elif row['exraid'].lower() == 'true':
                    valid_data['exraid'] = True
            rows.append(valid_data)
        insert.rows(rows)
        await insert.commit(do_update=True)

    async def stops_from_csv(self, guildid, file):
        bot = self.bot
        stops_table = bot.dbi.table('pokestops')
        insert = stops_table.insert()
        reader = csv.DictReader(codecs.iterdecode(file.readlines(), 'utf-8'))
        rows = []
        for row in reader:
            valid_data = {}
            valid_data['guild'] = guildid
            if isinstance(row.get('name'), str):
                valid_data['name'] = row['name']
            else:
                continue
            if isinstance(row.get('nickname'), str):
                valid_data['nickname'] = row.get('nickname')
            else:
                pass
            try:
                lat = float(row.get('lat'))
                lon = float(row.get('lon'))
            except:
                continue
            l10 = S2_L10.from_coords(bot, (lat, lon))
            valid_data['lat'] = lat
            valid_data['lon'] = lon
            valid_data['l10'] = l10.cellid
            rows.append(valid_data)
        insert.rows(rows)
        await insert.commit(do_update=True)
    
    async def add_gym(self, guild_id, name, lat, lon, exraid=False, nickname=None):
        gyms_table = self.bot.dbi.table('gyms')
        insert = gyms_table.insert()
        l10 = S2_L10.from_coords(self.bot, (lat, lon))
        d = {
            'guild': guild_id,
            'name': name,
            'lat': lat,
            'lon': lon,
            'l10': l10.cellid,
            'nickname': nickname,
            'exraid': exraid
        }
        insert.row(**d)
        await insert.commit()
    
    async def add_stop(self, guild_id, name, lat, lon, nickname=None):
        stops_table = self.bot.dbi.table('pokestops')
        insert = stops_table.insert()
        l10 = S2_L10.from_coords(self.bot, (lat, lon))
        d = {
            'guild': guild_id,
            'name': name,
            'lat': lat,
            'lon': lon,
            'l10': l10.cellid,
            'nickname': nickname
        }
        insert.row(**d)
        await insert.commit()
    
    @command()
    @commands.has_permissions(manage_guild=True)
    async def importgyms(self, ctx):
        attachment = ctx.message.attachments[0]
        guildid = ctx.guild.id
        bot = ctx.bot
        f = io.BytesIO()
        await attachment.save(f)
        await self.gyms_from_csv(guildid, f)
        await ctx.send("Import successful")

    @command()
    @commands.has_permissions(manage_guild=True)
    async def importstops(self, ctx):
        attachment = ctx.message.attachments[0]
        guildid = ctx.guild.id
        bot = ctx.bot
        f = io.BytesIO()
        await attachment.save(f)
        await self.stops_from_csv(guildid, f)
    
    @command()
    @commands.has_permissions(manage_guild=True)
    async def gym(self, ctx, name: str, lat: float, lon: float, *, nickname: str=None):
        guild_id = ctx.guild.id
        await self.add_gym(guild_id, name, lat, lon, nickname=nickname)
    
    @command()
    @commands.has_permissions(manage_guild=True)
    async def exraidgym(self, ctx, name: str, lat: float, lon: float, *, nickname: str=None):
        guild_id = ctx.guild.id
        await self.add_gym(guild_id, name, lat, lon, exraid=True, nickname=nickname)

    
    

    