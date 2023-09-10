#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nrrddate
Version:  0.0.4
Author:   Sean O'Connell <sean@sdoconnell.net>
License:  MIT
Homepage: https://github.com/sdoconnell/nrrddate
About:
A terminal-based calendar management tool with local file-based storage.

usage: nrrddate [-h] [-c <file>] for more help: nrrddate <command> -h ...

Terminal-based calendar management for nerds.

commands:
  (for more help: nrrddate <command> -h)
    archive             archive an event
    delete (rm)         delete an event file
    edit                edit an event file (uses $EDITOR)
    export              export events to iCalendar-formatted VEVENT output
    freebusy            export freebusy data to iCalendar-formatted VEVENT output
    ics                 process a received ICS file
    info                show info about an event
    invite              send meeting invites for an event
    list (ls)           list events
    modify (mod)        modify an event
    new                 create a new event
    notes               add/update notes on an event (uses $EDITOR)
    query               search events with structured text output
    reminders (rem)     event reminders
    search              search events
    shell               interactive shell
    unset               clear a field from a specified event
    version             show version info

optional arguments:
  -h, --help            show this help message and exit
  -c <file>, --config <file>
                        config file


Copyright © 2021 Sean O'Connell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
import argparse
import calendar as modcalendar  # name too commonly used
import configparser
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
import time
import uuid
from cmd import Cmd
from datetime import datetime, timedelta, date, timezone
from textwrap import TextWrapper

import icalendar
import tzlocal
import yaml
from dateutil import parser as dtparser
from dateutil.rrule import rrule as rr_rrule
from dateutil.rrule import MINUTELY, HOURLY, DAILY
from dateutil.rrule import WEEKLY, MONTHLY, YEARLY
from dateutil.rrule import SU, MO, TU, WE, TH, FR, SA
from rich import box
from rich.color import ColorParseError
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.style import Style
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

APP_NAME = "nrrddate"
APP_VERS = "0.0.3"
APP_COPYRIGHT = "Copyright © 2021 Sean O'Connell."
APP_LICENSE = "Released under MIT license."
DEFAULT_DURATION = 30
DEFAULT_REMINDER = "start-15m"
DEFAULT_FIRST_WEEKDAY = 6
DEFAULT_RECURRENCE_LIMIT = 250
DEFAULT_AB_QUERY_CMD = 'nrrdbook mutt %s'
DEFAULT_MAILER_CMD = 'echo %b | mutt -s %s -a %a -- %r'
DEFAULT_DATA_DIR = f"$HOME/.local/share/{APP_NAME}"
DEFAULT_CONFIG_FILE = f"$HOME/.config/{APP_NAME}/config"
DEFAULT_CONFIG = (
    "[main]\n"
    f"data_dir = {DEFAULT_DATA_DIR}\n"
    "# default event duration (in minutes)\n"
    f"default_duration = {DEFAULT_DURATION}\n"
    "# default event reminder expression\n"
    f"default_reminder = {DEFAULT_REMINDER}\n"
    "# first day of week (0 = Mon, 6 = Sun)\n"
    f"first_weekday = {DEFAULT_FIRST_WEEKDAY}\n"
    "# show calendars in week, month and year list views\n"
    "show_calendar_week = true\n"
    "show_calendar_month = true\n"
    "show_calendar_year = true\n"
    "# maximum number of recurrences for events\n"
    f"recurrence_limit = {DEFAULT_RECURRENCE_LIMIT}\n"
    "# custom address book query command\n"
    "# output must be in mutt query style and\n"
    "# command must include '%s' to represent\n"
    "# the query string for which to search.\n"
    f"#ab_query_cmd = {DEFAULT_AB_QUERY_CMD}\n"
    "# mailer command for sending meeting invites\n"
    "# command must include '%s' to represent the\n"
    "# email subject, '%a' to represent the .ics\n"
    "# attachment, '%b' the body, and '%r' to\n"
    "# represent the recipient address.\n"
    f"#mailer_cmd = {DEFAULT_MAILER_CMD}\n"
    "# set your name and email address for email-related functions\n"
    "# such as reminders, invites, and responses\n"
    "#user_name = Bob Roberts\n"
    "#user_email = bob@roberts.tld\n"
    "\n"
    "[colors]\n"
    "disable_colors = false\n"
    "disable_bold = false\n"
    "# set to 'true' if your terminal pager supports color\n"
    "# output and you would like color output when using\n"
    "# the '--pager' ('-p') option\n"
    "color_pager = false\n"
    "# custom colors\n"
    "#title = blue\n"
    "#description = default\n"
    "#location = default\n"
    "#organizer = default\n"
    "#calendar = bright_cyan\n"
    "#calendar_hl = yellow\n"
    "#alias = bright_black\n"
    "#tags = cyan\n"
    "#label = white\n"
    "#border = white\n"
    "#date = green\n"
    "#dateheader = blue\n"
    "#time = bright_green\n"
    "#flag = bright_yellow\n"
    "\n"
    "[calendar_colors]\n"
    "#default = default\n"
    "#personal = bright_blue\n"
    "#work = bright_green\n"
)


class Events():
    """Performs calendar event operations.

    Attributes:
        config_file (str):  application config file.
        data_dir (str):     directory containing calendar event files.
        dflt_config (str):  the default config if none is present.

    """
    def __init__(
            self,
            config_file,
            data_dir,
            dflt_config):
        """Initializes an Events() object."""
        self.config_file = config_file
        self.data_dir = data_dir
        self.config_dir = os.path.dirname(self.config_file)
        self.dflt_config = dflt_config
        self.interactive = False

        # default colors
        self.color_title = "bright_blue"
        self.color_description = "default"
        self.color_location = "default"
        self.color_organizer = "default"
        self.color_alias = "bright_black"
        self.color_tags = "cyan"
        self.color_label = "white"
        self.color_border = "white"
        self.color_date = "green"
        self.color_dateheader = "blue"
        self.color_time = "bright_green"
        self.color_flag = "bright_yellow"
        self.color_calendar = "bright_cyan"
        self.color_calendar_hl = "yellow"
        self.color_bold = True
        self.color_pager = False
        self.calendar_colors = None
        self.color_enabled = True

        # editor (required for some functions)
        self.editor = os.environ.get("EDITOR")

        # defaults
        self.ltz = tzlocal.get_localzone()
        self.default_duration = DEFAULT_DURATION
        self.default_reminder = DEFAULT_REMINDER
        self.first_weekday = DEFAULT_FIRST_WEEKDAY
        self.show_calendar_week = True
        self.show_calendar_month = True
        self.show_calendar_year = True
        self.recurrence_limit = DEFAULT_RECURRENCE_LIMIT
        self.user_name = None
        self.user_email = None
        self.ab_query_cmd = DEFAULT_AB_QUERY_CMD
        self.mailer_cmd = DEFAULT_MAILER_CMD
        self.add_reminders = None
        self.add_attendees = None
        self.add_organizer = None
        self.add_attachments = None

        # initial style definitions, these are updated after the config
        # file is parsed for custom colors
        self.style_title = None
        self.style_description = None
        self.style_location = None
        self.style_organizer = None
        self.style_alias = None
        self.style_tags = None
        self.style_label = None
        self.style_border = None
        self.style_date = None
        self.style_dateheader = None
        self.style_time = None
        self.style_flag = None
        self.style_calendar = None
        self.style_calendar_hl = None

        self._default_config()
        self._parse_config()
        self._verify_data_dir()
        self._parse_files()
        self._calc_master_view()

    def _alias_not_found(self, alias):
        """Report an invalid alias and exit or pass appropriately.

        Args:
            alias (str):    the invalid alias.

        """
        self._handle_error(f"Alias '{alias}' not found")

    def _calc_duration(self, expression):
        """Calculates the duration in seconds represented by an
        expression in the form (x)d(y)h(z)m, (y)h(z)m, or (z)m for days,
        hours, and minutes.

        Args:
            expression (str):   the duration expression.

        Returns:
            duration (int):      the duration in seconds.

        """
        expression = expression.lower()
        d_search = re.search(r"\d+d", expression)
        h_search = re.search(r"\d+h", expression)
        m_search = re.search(r"\d+m", expression)
        days = int(d_search[0].replace('d', '')) if d_search else 0
        hours = int(h_search[0].replace('h', '')) if h_search else 0
        minutes = int(m_search[0].replace('m', '')) if m_search else 0
        duration = (days*86400) + (hours*3600) + (minutes*60)

        if duration == 0:
            duration = self.default_duration*60

        return duration

    def _calc_end_dt(self, dt_start, end):
        """Given an event 'start' datetime object and 'end' datetime
        string or expression, calculates a datetime object representing
        the event end time.

        Args:
            dt_start (obj): the event 'start' datetime object.
            end (str):      a datetime-like string or an expression
        representing a time difference in the form (x)d(y)h(z)m.

        Returns:
            dt_end (obj):   the event 'end' datetime object.

        """
        # try to convert the 'end' string to a datetime obj
        dt_end = self._datetime_or_none(end)
        # if that fails, try to convert a +(x)d(y)h(z)m expression to a
        # valid datetime obj relative to the start time
        if not dt_end:
            if end.startswith('+'):
                dt_end = self._calc_relative_datetime(
                        dt_start, end.replace('+', ''))
            else:
                dt_end = self._calc_relative_datetime(
                        dt_start, end)
        # otherwise, fallback to the default event duration
        if not dt_end:
            dt_end = dt_start + timedelta(
                    minutes=self.default_duration)
        return dt_end

    def _calc_event_recurrences(self, rruleobj, dt_start, past=False):
        """Calculates all recurrences of an event given the start
        datetime and a recurrence rule.

        Args:
            rruleobj (dict):   a dict of recurrence rule parameters.
            dt_start (obj): the start datetime.
            past (bool):    include recurrences in the past.

        Returns:
            recurrences (list): a list of datetime objects.

        """
        now = datetime.now(tz=self.ltz)
        rr_freqstr = rruleobj.get('freq')
        frequencies = {
            'MINUTELY': MINUTELY,
            'HOURLY': HOURLY,
            'DAILY': DAILY,
            'WEEKLY': WEEKLY,
            'MONTHLY': MONTHLY,
            'YEARLY': YEARLY
        }
        weekdays = {
            'SU': SU,
            'MO': MO,
            'TU': TU,
            'WE': WE,
            'TH': TH,
            'FR': FR,
            'SA': SA
        }
        if rr_freqstr:
            rr_freqstr = rr_freqstr.upper()
            rr_freq = frequencies.get(rr_freqstr)
        else:
            rr_freq = None
        rr_count = rruleobj.get('count')
        if not rr_count:
            rr_count = self.recurrence_limit
        rr_until = rruleobj.get('until')
        rr_interval = rruleobj.get('interval')
        if not rr_interval:
            rr_interval = 1
        rr_byminute = rruleobj.get('byminute')
        rr_byhour = rruleobj.get('byhour')
        rr_byweekdaystr = rruleobj.get('byweekday')
        if rr_byweekdaystr:
            rr_byweekdaystr = rr_byweekdaystr.upper()
            rr_byweekday = weekdays.get(rr_byweekdaystr)
        else:
            rr_byweekday = None
        rr_bymonth = rruleobj.get('bymonth')
        rr_bymonthday = rruleobj.get('bymonthday')
        rr_byyearday = rruleobj.get('byyearday')
        rr_byweekno = rruleobj.get('byweekno')
        rr_bysetpos = rruleobj.get('bysetpos')
        rr_date = rruleobj.get('date')
        rr_except = rruleobj.get('except')

        if rr_freq:
            all_recurrences = list(rr_rrule(rr_freq,
                                            dtstart=dt_start,
                                            interval=rr_interval,
                                            wkst=self.first_weekday,
                                            count=rr_count,
                                            until=rr_until,
                                            bysetpos=rr_bysetpos,
                                            bymonth=rr_bymonth,
                                            bymonthday=rr_bymonthday,
                                            byyearday=rr_byyearday,
                                            byweekno=rr_byweekno,
                                            byweekday=rr_byweekday,
                                            byhour=rr_byhour,
                                            byminute=rr_byminute))
            # add any specifically defined recurrences
            if rr_date:
                for entry in rr_date:
                    new_dt = self._datetime_or_none(entry)
                    if new_dt:
                        if new_dt not in all_recurrences:
                            all_recurrences.append(new_dt)
            # remove any specifically excluded recurences
            if rr_except:
                for entry in rr_except:
                    new_dt = self._datetime_or_none(entry)
                    if new_dt:
                        if new_dt in all_recurrences:
                            all_recurrences.remove(new_dt)

            all_recurrences.sort()

            if past:
                recurrences = all_recurrences.copy()
            else:
                recurrences = []
                # remove any entries that are in the past
                for entry in all_recurrences:
                    if entry >= now:
                        recurrences.append(entry)
        else:
            recurrences = None

        return recurrences

    def _calc_master_view(self):
        """Calculates all occurences of all events into a master view."""
        unsorted_view = []
        for entry in self.events:
            event = self.parse_event(entry)
            duration = event['end'] - event['start']
            if event['rrule'] and event['start']:
                recurrences = self._calc_event_recurrences(
                        event['rrule'], event['start'], past=True)
                if recurrences:
                    for recur in recurrences:
                        data = {}
                        data['uid'] = entry
                        data['start'] = recur
                        data['end'] = recur + duration
                        unsorted_view.append(data)
                # a problem occurred processing the rrule
                else:
                    data = {}
                    data['uid'] = entry
                    data['start'] = event['start']
                    data['end'] = event['end']
                    unsorted_view.append(data)
            else:
                data = {}
                data['uid'] = entry
                data['start'] = event['start']
                data['end'] = event['end']
                unsorted_view.append(data)
        self.master_view = sorted(unsorted_view, key=lambda x: x['start'])

    def _calc_relative_datetime(self, reference, duration, prior=False):
        """Calculates a relative datetime using a reference time and an
        expression in the form (x)d(y)h(z)m, (y)h(z)m, or (z)m for days,
        hours, and minutes.

        Args:
            reference (obj):    datetime object for the reference time.
            duration (int):     duration expression.
            prior (bool):       the relative datetime should be
        calculated prior to the reference datetime.

        Returns:
            reminder (obj):     datetime object for the reminder.

        """
        if not isinstance(duration, int):
            seconds = self._calc_duration(duration)
        else:
            seconds = duration*60
        if prior:
            relative = reference - timedelta(seconds=seconds)
        else:
            relative = reference + timedelta(seconds=seconds)

        return relative

    def _calc_reminder(self, reminder, dt_start=None, dt_end=None):
        """Calculates a reminder datetime object given a reminder
        expression and start or end datetime object.

        Args:
            reminder (str): the reminder expression.
            dt_start (obj): the event start datetime.
            dt_end (obj):   the event end datetime.

        Returns:
            dt_reminder (obj):  the reminder datetime.

        """
        reminder = reminder.lower()
        dt_reminder = self._datetime_or_none(reminder)
        if not dt_reminder:
            if '-' in reminder:
                split = '-'
                prior = True
                parse = True
            elif '+' in reminder:
                split = '+'
                prior = False
                parse = True
            else:
                parse = False
            if parse:
                reminder = reminder.split(split)
                if reminder[0] == "start" and dt_start:
                    dt_reminder = self._calc_relative_datetime(
                            dt_start, reminder[1], prior)
                elif reminder[0] == "end" and dt_end:
                    dt_reminder = self._calc_relative_datetime(
                            dt_end, reminder[1], prior)
                else:
                    dt_reminder = None

        return dt_reminder

    def _datetime_or_none(self, timestr):
        """Verify a datetime object or a datetime string in ISO format
        and return a datetime object or None.

        Args:
            timestr (str): a datetime formatted string.

        Returns:
            timeobj (datetime): a valid datetime object or None.

        """
        if isinstance(timestr, datetime):
            timeobj = timestr.astimezone(tz=self.ltz)
        else:
            try:
                timeobj = dtparser.parse(timestr).astimezone(tz=self.ltz)
            except (TypeError, ValueError, dtparser.ParserError):
                timeobj = None
        return timeobj

    def _default_config(self):
        """Create a default configuration directory and file if they
        do not already exist.
        """
        if not os.path.exists(self.config_file):
            try:
                os.makedirs(self.config_dir, exist_ok=True)
                with open(self.config_file, "w",
                          encoding="utf-8") as config_file:
                    config_file.write(self.dflt_config)
            except IOError:
                self._error_exit(
                    "Config file doesn't exist "
                    "and can't be created.")

    @staticmethod
    def _error_exit(errormsg):
        """Print an error message and exit with a status of 1

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')
        sys.exit(1)

    @staticmethod
    def _error_pass(errormsg):
        """Print an error message but don't exit.

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')

    @staticmethod
    def _export_timestamp(timeobj):
        """Print a datetime string in iCalendar-compatible format.

        Args:
            timeobj (obj):  a datetime object.

        Returns:
            timestr (str):  a datetime string.

        """
        timestr = (timeobj.astimezone(tz=timezone.utc)
                   .strftime("%Y%m%dT%H%M%SZ"))
        return timestr

    def _format_event(self, event):
        """Formats event output for a given event.

        Args:
            event (dict):   the event data to format.

        Returns:
            output (str):   the formatted output.

        """
        startdate = event['start'].date()
        enddate = event['end'].date()
        start = event['start'].strftime("%H:%M")
        if startdate == enddate:
            end = event['end'].strftime("%H:%M")
        else:
            end = event['end'].strftime("%Y-%m-%d %H:%M")
        alias = event['alias']
        calendar = event['calendar']
        description = event['description']
        location = event['location']
        tags = event['tags']
        notes = event['notes']
        rrule = event['rrule']

        # primary line
        if notes:
            notesflag = Text("*")
            notesflag.stylize(self.style_flag)
        else:
            notesflag = ""

        if rrule:
            rruleflag = Text("@")
            rruleflag.stylize(self.style_flag)
        else:
            rruleflag = ""

        if calendar:
            if calendar != "default":
                calendartxt = Text(f"[{calendar}] ")
                calendartxt.stylize(self._make_calendar_style(calendar))
            else:
                calendartxt = ""
        else:
            calendartxt = ""

        if description:
            descriptiontxt = Text(description)
            descriptiontxt.stylize(self.style_description)
        else:
            descriptiontxt = ""

        aliastxt = Text(f"({alias}) ")
        aliastxt.stylize(self.style_alias)

        # tag line
        if tags:
            taglabel = Text("tags: ")
            taglabel.stylize(self.style_label)
            tagfield = Text(','.join(tags))
            tagfield.stylize(self.style_tags)
            tagline = Text.assemble(
                "   + ", taglabel, tagfield)
        else:
            tagline = ""

        # location line
        if location:
            locationlabel = Text("location: ")
            locationlabel.stylize(self.style_label)
            locationtxt = Text(location)
            locationtxt.stylize(self.style_location)
            locationline = Text.assemble(
                "   + ", locationlabel, locationtxt)
        else:
            locationline = ""

        newline1 = "\n" if tags or location else ""
        newline2 = "\n" if tags and location else ""

        startdate = Text(start)
        startdate.stylize(self.style_time)

        enddate = Text(end)
        enddate.stylize(self.style_time)

        dateline = Text.assemble(
            startdate,
            '-',
            enddate)

        # assemble lines into event block
        output = Text.assemble(
            "- ",
            dateline,
            rruleflag,
            " ",
            aliastxt,
            calendartxt,
            descriptiontxt,
            notesflag,
            newline1,
            locationline,
            newline2,
            tagline)

        return output

    @staticmethod
    def _format_timestamp(timeobj, pretty=False):
        """Convert a datetime obj to a string.

        Args:
            timeobj (datetime): a datetime object.
            pretty (bool):      return a pretty formatted string.

        Returns:
            timestamp (str): "%Y-%m-%d %H:%M:%S" or "%Y-%m-%d[ %H:%M]".

        """
        if pretty:
            if timeobj.strftime("%H:%M") == "00:00":
                timestamp = timeobj.strftime("%Y-%m-%d")
            else:
                timestamp = timeobj.strftime("%Y-%m-%d %H:%M")
        else:
            timestamp = timeobj.strftime("%Y-%m-%d %H:%M:%S")
        return timestamp

    def _gen_alias(self):
        """Generates a new alias and check for collisions.

        Returns:
            alias (str):    a randomly-generated alias.

        """
        aliases = self._get_aliases()
        chars = string.ascii_lowercase + string.digits
        while True:
            alias = ''.join(random.choice(chars) for x in range(4))
            if alias not in aliases:
                break
        return alias

    def _generate_month_calendar(self, year, month, events):
        """Generates a formatted monthly calendar with event
        days highlighted.

        Args:
            year (int): the calendar year.
            month (int): the calendar month.
            events (dict): the events for a datetime range.

        Returns:
            cal_txt (obj): a formatted Text object.

        """
        modcalendar.setfirstweekday(self.first_weekday)
        months = list(modcalendar.month_name)

        cal_title_style = Style(color=self.color_calendar,
                                bold=self.color_bold)
        cal_days_style = Style(color=self.color_calendar,
                               underline=True)
        month_hdr = Text(f"{months[month]} {year}\n",
                         style=cal_title_style, justify='center')
        month_day_line = Text(modcalendar.weekheader(2),
                              style=cal_days_style)
        month_txt = Text("")
        for week in modcalendar.monthcalendar(year, month):
            week_txt = Text("")
            for day in week:
                if day == 0:
                    day_txt = "  "
                else:
                    highlight = False
                    for event in events:
                        if (date(year, month, day) ==
                                event['start'].date()):
                            highlight = True
                    if highlight:
                        day_txt = Text(
                                f"{day:02d}",
                                style=self.style_calendar_hl)
                    else:
                        day_txt = Text(
                                f"{day:02d}",
                                style=self.style_calendar)
                if week.index(day) != week[:-1]:
                    week_txt = Text.assemble(week_txt, day_txt, " ")
                else:
                    week_txt = Text.assemble(week_txt, day_txt)
            month_txt = Text.assemble(month_txt, week_txt, "\n")
        cal_txt = Text.assemble(
            month_hdr,
            "\n",
            month_day_line,
            "\n",
            month_txt)
        return cal_txt

    def _get_aliases(self):
        """Generates a list of all event aliases.

        Returns:
            aliases (list): the list of all event aliases.

        """
        aliases = []
        for event in self.events:
            alias = self.events[event].get('alias')
            if alias:
                aliases.append(alias.lower())
        return aliases

    def _handle_error(self, msg):
        """Reports an error message and conditionally handles error exit
        or notification.

        Args:
            msg (str):  the error message.

        """
        if self.interactive:
            self._error_pass(msg)
        else:
            self._error_exit(msg)

    @staticmethod
    def _integer_or_default(inputdata, default=None):
        """Verify an input data and return an integer or a default
        value (or None).

        Args:
            inputdata (str): a string or number.
            default (int or None):  a default to use if there is an
        exception.

        Returns:
            output (int): a verified integer, a default value, or None.

        """
        try:
            output = int(inputdata)
        except (ValueError, TypeError):
            output = default
        return output

    def _make_calendar_style(self, calendar):
        """Create a style for a calendar label based on values in
        self.calendar_colors.

        Args:
            calendar (str): the calendar name to stylize.

        Returns:
            this_style (obj): Rich Style() object.

        """
        color = self.calendar_colors.get(calendar)
        if color and self.color_enabled:
            try:
                this_style = Style(color=color)
            except ColorParseError:
                this_style = Style(color="default")
        else:
            this_style = Style(color="default")

        return this_style

    def _parse_config(self):
        """Read and parse the configuration file."""
        config = configparser.ConfigParser()
        if os.path.isfile(self.config_file):
            try:
                config.read(self.config_file)
            except configparser.Error:
                self._error_exit("Error reading config file")

            if "main" in config:
                if config["main"].get("data_dir"):
                    self.data_dir = os.path.expandvars(
                        os.path.expanduser(
                            config["main"].get("data_dir")))

                if config["main"].get("default_duration"):
                    try:
                        self.default_duration = int(
                                config["main"].get("default_duration"))
                    except ValueError:
                        self.default_duration = DEFAULT_DURATION

                if config["main"].get("default_reminder"):
                    self.default_reminder = (
                            config["main"].get("default_reminder",
                                               DEFAULT_REMINDER))

                if config["main"].get("first_weekday"):
                    try:
                        self.first_weekday = int(
                                config["main"].get("first_weekday"))
                    except ValueError:
                        self.first_weekday = DEFAULT_FIRST_WEEKDAY

                if config["main"].get("show_calendar_week"):
                    try:
                        self.show_calendar_week = (config["main"]
                                                   .getboolean(
                                                       "show_calendar_week",
                                                       True))
                    except ValueError:
                        self.show_calendar_week = True

                if config["main"].get("show_calendar_month"):
                    try:
                        self.show_calendar_month = (config["main"]
                                                    .getboolean(
                                                        "show_calendar_month",
                                                        True))
                    except ValueError:
                        self.show_calendar_month = True

                if config["main"].get("show_calendar_year"):
                    try:
                        self.show_calendar_year = (config["main"]
                                                   .getboolean(
                                                       "show_calendar_year",
                                                       True))
                    except ValueError:
                        self.show_calendar_year = True

                if config["main"].get("recurrence_limit"):
                    try:
                        self.recurrence_limit = int(
                                config["main"].get("recurrence_limit"))
                    except ValueError:
                        self.recurrence_limit = DEFAULT_RECURRENCE_LIMIT

                self.user_name = config["main"].get("user_name")
                self.user_email = config["main"].get("user_email")
                self.ab_query_cmd = config["main"].get("ab_query_cmd",
                                                       DEFAULT_AB_QUERY_CMD,
                                                       raw=True)
                self.mailer_cmd = (
                        config["main"].get("mailer_cmd",
                                           DEFAULT_MAILER_CMD,
                                           raw=True))

            def _apply_colors():
                """Try to apply custom colors and catch exceptions for
                invalid color names.
                """
                try:
                    self.style_title = Style(
                        color=self.color_title,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_description = Style(
                        color=self.color_description)
                except ColorParseError:
                    pass
                try:
                    self.style_location = Style(
                        color=self.color_location)
                except ColorParseError:
                    pass
                try:
                    self.style_organizer = Style(
                        color=self.color_organizer)
                except ColorParseError:
                    pass
                try:
                    self.style_alias = Style(
                        color=self.color_alias)
                except ColorParseError:
                    pass
                try:
                    self.style_tags = Style(
                        color=self.color_tags)
                except ColorParseError:
                    pass
                try:
                    self.style_label = Style(
                        color=self.color_label)
                except ColorParseError:
                    pass
                try:
                    self.style_border = Style(
                        color=self.color_border)
                except ColorParseError:
                    pass
                try:
                    self.style_date = Style(
                        color=self.color_date)
                except ColorParseError:
                    pass
                try:
                    self.style_dateheader = Style(
                        color=self.color_dateheader,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_time = Style(
                        color=self.color_time)
                except ColorParseError:
                    pass
                try:
                    self.style_flag = Style(
                        color=self.color_flag,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_calendar = Style(
                        color=self.color_calendar)
                except ColorParseError:
                    pass
                try:
                    self.style_calendar_hl = Style(
                        color=self.color_calendar_hl,
                        bold=self.color_bold)
                except ColorParseError:
                    pass

            # apply default colors
            _apply_colors()

            if "colors" in config:
                # custom colors with fallback to defaults
                self.color_title = (
                    config["colors"].get(
                        "title", "bright_blue"))
                self.color_description = (
                    config["colors"].get(
                        "description", "default"))
                self.color_location = (
                    config["colors"].get(
                        "location", "default"))
                self.color_organizer = (
                    config["colors"].get(
                        "organizer", "default"))
                self.color_alias = (
                    config["colors"].get(
                        "alias", "bright_black"))
                self.color_tags = (
                    config["colors"].get(
                        "tags", "cyan"))
                self.color_label = (
                    config["colors"].get(
                        "label", "white"))
                self.color_border = (
                    config["colors"].get(
                        "border", "white"))
                self.color_date = (
                    config["colors"].get(
                        "date", "green"))
                self.color_dateheader = (
                    config["colors"].get(
                        "dateheader", "blue"))
                self.color_time = (
                    config["colors"].get(
                        "time", "bright_green"))
                self.color_flag = (
                    config["colors"].get(
                        "flag", "bright_yellow"))
                self.color_calendar = (
                    config["colors"].get(
                        "calendar", "bright_cyan"))
                self.color_calendar_hl = (
                    config["colors"].get(
                        "calendar_hl", "yellow"))

                # color paging (disabled by default)
                self.color_pager = config["colors"].getboolean(
                    "color_pager", "False")

                # disable colors
                if bool(config["colors"].getboolean("disable_colors")):
                    self.color_enabled = False
                    self.color_title = "default"
                    self.color_description = "default"
                    self.color_location = "default"
                    self.color_organizer = "default"
                    self.color_alias = "default"
                    self.color_tags = "default"
                    self.color_label = "default"
                    self.color_border = "default"
                    self.color_date = "default"
                    self.color_dateheader = "default"
                    self.color_time = "default"
                    self.color_flag = "default"
                    self.color_calendar = "default"
                    self.color_calendar_hl = "default"

                # disable bold
                if bool(config["colors"].getboolean("disable_bold")):
                    self.color_bold = False

                # try to apply requested custom colors
                _apply_colors()

            if "calendar_colors" in config:
                calendar_colors = config["calendar_colors"]
                self.calendar_colors = {}
                for cal in calendar_colors:
                    self.calendar_colors[cal] = calendar_colors.get(cal)
        else:
            self._error_exit("Config file not found")

    def _parse_files(self):
        """ Read calendar event files from `data_dir` and parse event
        data into`events`.

        Returns:
            events (dict):    parsed data from each event file

        """
        this_event_files = {}
        this_events = {}
        aliases = {}

        with os.scandir(self.data_dir) as entries:
            for entry in entries:
                if entry.name.endswith('.yml') and entry.is_file():
                    fullpath = entry.path
                    data = None
                    try:
                        with open(fullpath, "r",
                                  encoding="utf-8") as entry_file:
                            data = yaml.safe_load(entry_file)
                    except (OSError, IOError, yaml.YAMLError):
                        self._error_pass(
                            f"failure reading or parsing {fullpath} "
                            "- SKIPPING")
                    if data:
                        uid = None
                        event = data.get("event")
                        if event:
                            uid = event.get("uid")
                            alias = event.get("alias")
                            start = event.get("start")
                            add_event = True
                            if uid:
                                # duplicate UID detection
                                dupid = this_event_files.get(uid)
                                if dupid:
                                    self._error_pass(
                                        "duplicate UID detected:\n"
                                        f"  {uid}\n"
                                        f"  {dupid}\n"
                                        f"  {fullpath}\n"
                                        f"SKIPPING {fullpath}")
                                    add_event = False
                            if alias:
                                # duplicate alias detection
                                dupalias = aliases.get(alias)
                                if dupalias:
                                    self._error_pass(
                                        "duplicate alias detected:\n"
                                        f"  {alias}\n"
                                        f"  {dupalias}\n"
                                        f"  {fullpath}\n"
                                        f"SKIPPING {fullpath}")
                                    add_event = False
                            # every event must have a valid start datetime
                            if not start:
                                self._error_pass(
                                    "no start param in {fullpath} - "
                                    "SKIPPING")
                                add_event = False
                            else:
                                test_start = self._datetime_or_none(start)
                                if not test_start:
                                    self._error_pass(
                                        "invalid start param in {fullpath} - "
                                        "SKIPPING")
                                    add_event = False
                            if add_event:
                                if alias and uid:
                                    this_events[uid] = event
                                    this_event_files[uid] = fullpath
                                    aliases[alias] = fullpath
                                else:
                                    self._error_pass(
                                        "no uid and/or alias param "
                                        f"in {fullpath} - SKIPPING")
                        else:
                            self._error_pass(
                                f"no data in {fullpath} - SKIPPING")
        self.events = this_events.copy()
        self.event_files = this_event_files.copy()

    def _print_event_list(
            self,
            events,
            view,
            pager=False,
            weekstart=None,
            month=None,
            year=None,
            cal_filter=None):
        """Print the formatted events list.

        Args:
            events (list):   the list of events (dicts) to be printed in
        a formatted manner.
            view (str):     the view to display (e.g., day, month, etc.)
            pager (bool):   whether or not to page output (default no).
            weekstart (obj): datetime object of the first day in the week.
            month (int):    the month for the current view.
            year (int):     the year for the current view.
            cal_filter (str): filter for events.

        """
        console = Console()
        if cal_filter:
            title = f"Events - {view} ({cal_filter})"
        else:
            title = f"Events - {view}"
        # table
        event_table = Table(
            title=title,
            title_style=self.style_title,
            title_justify="left",
            box=box.SIMPLE,
            show_header=False,
            show_lines=False,
            pad_edge=False,
            min_width=len(title),
            collapse_padding=False,
            padding=(0, 0, 0, 0))
        # single column
        event_table.add_column("column1")
        if (view.endswith("week") and
                weekstart and
                self.show_calendar_week):
            day1 = weekstart
            day2 = weekstart + timedelta(days=1)
            day3 = weekstart + timedelta(days=2)
            day4 = weekstart + timedelta(days=3)
            day5 = weekstart + timedelta(days=4)
            day6 = weekstart + timedelta(days=5)
            day7 = weekstart + timedelta(days=6)
            week_table = Table(
                title=None,
                box=box.SQUARE,
                show_header=True,
                header_style=self.style_dateheader,
                border_style=self.style_border,
                show_lines=False,
                pad_edge=True,
                collapse_padding=False,
                padding=(0, 0, 0, 0))
            week_table.add_column(
                day1.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            week_table.add_column(
                day2.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            week_table.add_column(
                day3.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            week_table.add_column(
                day4.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            week_table.add_column(
                day5.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            week_table.add_column(
                day6.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            week_table.add_column(
                day7.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            daytxt = {}
            day = 1
            for weekday in [day1, day2, day3, day4, day5, day6, day7]:
                highlight = False
                for event in events:
                    if weekday == event['start'].date():
                        highlight = True
                if highlight:
                    daytxt[day] = Text(
                            weekday.strftime("%m-%d"),
                            style=self.style_calendar_hl)
                else:
                    daytxt[day] = Text(
                            weekday.strftime("%m-%d"),
                            style=self.style_calendar)
                day += 1

            week_table.add_row(
                daytxt[1],
                daytxt[2],
                daytxt[3],
                daytxt[4],
                daytxt[5],
                daytxt[6],
                daytxt[7])
            event_table.add_row(week_table)
            event_table.add_row(" ")
        elif (view.endswith('month') and
                year and
                month and
                self.show_calendar_month):
            month_table = Table(
                title=None,
                box=box.SQUARE,
                show_header=False,
                border_style=self.style_border,
                show_lines=False,
                pad_edge=True,
                collapse_padding=False,
                padding=(1, 0, 0, 1))
            month_table.add_column("single")
            month_table.add_row(
                    self._generate_month_calendar(year, month, events))
            event_table.add_row(month_table)
            event_table.add_row(" ")
        elif (view.endswith('year') and
                year and
                self.show_calendar_year):
            modcalendar.setfirstweekday(self.first_weekday)
            year_table = Table(
                title=None,
                box=box.SQUARE,
                show_header=False,
                border_style=self.style_border,
                show_lines=True,
                pad_edge=True,
                collapse_padding=False,
                padding=(1, 0, 0, 1))
            if console.width >= 95:
                # four-column calendar view
                year_table.add_column("one")
                year_table.add_column("two")
                year_table.add_column("three")
                year_table.add_column("four")
                year_table.add_row(
                    self._generate_month_calendar(year, 1, events),
                    self._generate_month_calendar(year, 2, events),
                    self._generate_month_calendar(year, 3, events),
                    self._generate_month_calendar(year, 4, events))
                year_table.add_row(
                    self._generate_month_calendar(year, 5, events),
                    self._generate_month_calendar(year, 6, events),
                    self._generate_month_calendar(year, 7, events),
                    self._generate_month_calendar(year, 8, events))
                year_table.add_row(
                    self._generate_month_calendar(year, 9, events),
                    self._generate_month_calendar(year, 10, events),
                    self._generate_month_calendar(year, 11, events),
                    self._generate_month_calendar(year, 12, events))
                event_table.add_row(year_table)
                event_table.add_row(" ")
            elif console.width >= 72:
                # three-column calendar view
                year_table.add_column("one")
                year_table.add_column("two")
                year_table.add_column("three")
                year_table.add_row(
                    self._generate_month_calendar(year, 1, events),
                    self._generate_month_calendar(year, 2, events),
                    self._generate_month_calendar(year, 3, events))
                year_table.add_row(
                    self._generate_month_calendar(year, 4, events),
                    self._generate_month_calendar(year, 5, events),
                    self._generate_month_calendar(year, 6, events))
                year_table.add_row(
                    self._generate_month_calendar(year, 7, events),
                    self._generate_month_calendar(year, 8, events),
                    self._generate_month_calendar(year, 9, events))
                year_table.add_row(
                    self._generate_month_calendar(year, 10, events),
                    self._generate_month_calendar(year, 11, events),
                    self._generate_month_calendar(year, 12, events))
                event_table.add_row(year_table)
                event_table.add_row(" ")
            else:
                # two-column calendar view
                year_table.add_column("one")
                year_table.add_column("two")
                year_table.add_row(
                    self._generate_month_calendar(year, 1, events),
                    self._generate_month_calendar(year, 2, events))
                year_table.add_row(
                    self._generate_month_calendar(year, 3, events),
                    self._generate_month_calendar(year, 4, events))
                year_table.add_row(
                    self._generate_month_calendar(year, 5, events),
                    self._generate_month_calendar(year, 6, events))
                year_table.add_row(
                    self._generate_month_calendar(year, 7, events),
                    self._generate_month_calendar(year, 8, events))
                year_table.add_row(
                    self._generate_month_calendar(year, 9, events),
                    self._generate_month_calendar(year, 10, events))
                year_table.add_row(
                    self._generate_month_calendar(year, 11, events),
                    self._generate_month_calendar(year, 12, events))
                event_table.add_row(year_table)
                event_table.add_row(" ")
        # event list
        if events:
            current_date = None
            for index, event in enumerate(events):
                if not current_date == event['start']:
                    current_date = event['start']
                    if index != 0:
                        event_table.add_row(" ")
                    datetxt = Text(event['start'].strftime("%A, %Y-%m-%d"))
                    datetxt.stylize(self.style_dateheader)
                    event_table.add_row(datetxt)
                fevent = self._format_event(event)
                event_table.add_row(fevent)
        else:
            event_table.add_row("None")
        # single-column layout
        layout = Table.grid()
        layout.add_column("single")
        layout.add_row("")
        layout.add_row(event_table)

        # render the output with a pager if -p
        if pager:
            if self.color_pager:
                with console.pager(styles=True):
                    console.print(layout)
            else:
                with console.pager():
                    console.print(layout)
        else:
            console.print(layout)

    def _sort_events(self, events, reverse=False):
        """Sort a list of events by date and return a sorted dict.

        Args:

            events (list):   the events to sort.
            reverse (bool): sort in reverse (optional).

        Returns:
            uids (dict):    a sorted dict of events.

        """
        fifouids = {}
        for uid in events:
            sort = self.events[uid].get('start')
            fifouids[uid] = sort
        sortlist = sorted(
            fifouids.items(), key=lambda x: x[1], reverse=reverse
        )
        uids = dict(sortlist)
        return uids

    def _uid_from_alias(self, alias):
        """Get the uid for a valid alias.

        Args:
            alias (str):    The alias of the event for which to find uid.

        Returns:
            uid (str or None): The uid that matches the submitted alias.

        """
        alias = alias.lower()
        uid = None
        for event in self.events:
            this_alias = self.events[event].get("alias")
            if this_alias:
                if this_alias == alias:
                    uid = event
        return uid

    @staticmethod
    def _validate_start_end(dt_start, dt_end):
        """Validate that the start datetime is before the end datetime.

        Args:
            dt_start (obj): the datetime object for the event start time.
            dt_end (obj):   the datetime object for the event end time.

        Returns:
            valid_start (bool): whether the start datetime is valid.

        """
        valid_start = dt_start < dt_end
        return valid_start

    def _verify_data_dir(self):
        """Create the events data directory if it doesn't exist."""
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)
            except IOError:
                self._error_exit(
                    f"{self.data_dir} doesn't exist "
                    "and can't be created")
        elif not os.path.isdir(self.data_dir):
            self._error_exit(f"{self.data_dir} is not a directory")
        elif not os.access(self.data_dir,
                           os.R_OK | os.W_OK | os.X_OK):
            self._error_exit(
                "You don't have read/write/execute permissions to "
                f"{self.data_dir}")

    @staticmethod
    def _write_yaml_file(data, filename):
        """Write YAML data to a file.

        Args:
            data (dict):    the structured data to write.
            filename (str): the location to write the data.

        """
        with open(filename, "w",
                  encoding="utf-8") as out_file:
            yaml.dump(
                data,
                out_file,
                default_flow_style=False,
                sort_keys=False)

    def add_another_reminder(self):
        """Asks if the user wants to add another reminder."""
        another = input("Add another reminder? [N/y]: ").lower()
        if another in ['y', 'yes']:
            self.add_new_reminder()

    def add_confirm_reminder(
            self,
            remind,
            notify,
            another=True):
        """Confirms the reminder expression provided.

        Args:
            remind (str):   the reminder date or expression.
            notify (int):   1 (display) or 2 (email)
            another (bool): offer to add another when complete.

        """
        if not remind:
            self._error_pass("reminder date/expression "
                             "cannot be empty")
            self.add_new_reminder(another)
        else:
            if notify == 1:
                notify = 'display'
            else:
                notify = 'email'
            print(
                "\n"
                "  New reminder:\n"
                f"    dt/expr: {remind}\n"
                f"    notify by: {notify}\n"
            )
            confirm = input("Is this correct? [N/y]: ").lower()
            if confirm in ['y', 'yes']:
                data = [remind, notify]
                if not self.add_reminders:
                    self.add_reminders = []
                self.add_reminders.append(data)
                if another:
                    self.add_another_reminder()
            else:
                self.add_new_reminder(another)

    def add_new_reminder(self, another=True):
        """Prompts the user through adding a new event reminder.

        Args:
            another (bool): offer to add another when complete.

        """
        remind = input("Reminder date/time or expression? "
                       "[default]: ") or self.default_reminder
        notify = input("Notify by (1) display, "
                       "or (2) email [1]: ") or 1
        try:
            notify = int(notify)
        except ValueError:
            notify = 1
        if notify not in [1, 2]:
            notify = 1
        self.add_confirm_reminder(remind, notify, another)

    def add_attendee_from_ab(self, another=True):
        """Query address book for the attendee to add.

        Args:
            another (bool): offer to add another when complete.

        """
        query_str = input("Query: ") or None
        if not query_str:
            self.add_attendee_from_ab(another)
        else:
            query_cmd = self.ab_query_cmd.split()
            query_cmd = [query_str if item == '%s'
                         else item for item in query_cmd]
            query_cmd = ' '.join(query_cmd)
            query = subprocess.run(
                    query_cmd,
                    capture_output=True,
                    check=True,
                    shell=True)
            results = query.stdout.decode('utf-8').split('\n')
            del results[0]
            del results[-1]
            if len(results) == 1:
                line = results[0].split('\t')
                att_name = line[1]
                att_email = line[0]
                print(att_name, att_email)
                att_status = input(
                    "Attendee status? [none]: ") or None
                self.add_confirm_attendee(att_name,
                                          att_email,
                                          att_status,
                                          another)
            elif len(results) > 0:
                item = 0
                for entry in results:
                    item += 1
                    line = entry.split('\t')
                    this_name = line[1]
                    this_email = line[0]
                    print(f"{item}. {this_name} "
                          f"<{this_email}>")
                choice = input("Choose number "
                               "(or other to cancel): ") or None
                if not choice and another:
                    self.add_another_attendee()
                else:
                    try:
                        choice = int(choice)
                    except ValueError:
                        if another:
                            self.add_another_attendee()
                    else:
                        if choice <= len(results):
                            choice -= 1
                            chosen = results[choice].split('\t')
                            att_name = chosen[1]
                            att_email = chosen[0]
                            att_status = input(
                                "Attendee status? [none]: "
                            ) or None
                            self.add_confirm_attendee(att_name,
                                                      att_email,
                                                      att_status,
                                                      another)
                        else:
                            if another:
                                self.add_another_attendee()

    def add_another_attendee(self):
        """Asks if the user wants to add another attendee."""
        another = input("Add another attendee? [N/y]: ").lower()
        if another in ['y', 'yes']:
            self.add_new_attendee()

    def add_confirm_attendee(
            self,
            att_name,
            att_email,
            att_status,
            another=True):
        """Confirms the attendee information provided.

        Args:
            att_name (str):   the attendee's name.
            att_email (str):  the attendee's email address.
            att_status (str): the attendee's status.
            another (bool): offer to add another when complete.

        """
        if not att_name:
            self._error_pass("attendee name cannot be empty")
            self.add_new_attendee(another)
        else:
            if not att_email:
                email_str = 'none'
            else:
                email_str = att_email
            if not att_status:
                status_str = 'none'
            else:
                status_str = att_status.lower()
            print(
                "\n"
                "  New attendee:\n"
                f"    name:   {att_name}\n"
                f"    email:  {email_str}\n"
                f"    status: {status_str}\n"
            )
            confirm = input("Is this correct? [N/y]: ").lower()
            if confirm in ['y', 'yes']:
                data = [att_name]
                if att_email:
                    data.append(att_email)
                if att_status:
                    data.append(att_status)
                if not self.add_attendees:
                    self.add_attendees = []
                self.add_attendees.append(data)
                if another:
                    self.add_another_attendee()
            else:
                self.add_new_attendee(another)

    def add_new_attendee(self, another=True):
        """Prompts the user through adding a new event attendee.

        Args:
            another (bool): offer to add another when complete.

        """
        from_ab = input("Add from address book? [N/y]: ").lower()
        if from_ab in ['y', 'yes']:
            self.add_attendee_from_ab(another)
        else:
            att_name = input("Attendee name? [none]: ") or None
            att_email = input("Attendee email? [none]: ") or None
            att_status = input("Attendee status? [none]: ") or None
            self.add_confirm_attendee(
                    att_name,
                    att_email,
                    att_status,
                    another=another)

    def add_another_attachment(self):
        """Asks if the user wants to add another attachment."""
        another = input("Add another attachment? [N/y]: ").lower()
        if another in ['y', 'yes']:
            self.add_new_attachment()

    def add_confirm_attachment(self, attachment, another=True):
        """Confirms the attachment URL provided.

        Args:
            attachment (str):   the attachment URL.
            another (bool): offer to add another when complete.

        """
        if not attachment:
            self._error_pass("attachment URL cannot be empty")
            self.add_new_attachment(another)
        else:
            print(
                "\n"
                "  New attachment:\n"
                f"    url:  {attachment}\n"
            )
            confirm = input("Is this correct? [N/y]: ").lower()
            if confirm in ['y', 'yes']:
                if not self.add_attachments:
                    self.add_attachments = []
                self.add_attachments.append(attachment)
                if another:
                    self.add_another_attachment()
            else:
                self.add_new_attachment(another)

    def add_new_attachment(self, another=True):
        """Prompts the user through adding a new event
        attachment.

        Args:
            another (bool): offer to add another when complete.

        """
        attachment = input("Attachment URL? [none]: ") or None
        self.add_confirm_attachment(attachment, another)

    def add_confirm_organizer(
            self,
            org_name,
            org_email):
        """Confirms the attendee information provided.

        Args:
            att_name (str):   the attendee's name.
            att_email (str):  the attendee's email address.

        """
        if not org_email or not org_name:
            self._error_pass("organizer name or email cannot be empty")
            self.add_new_organizer()
        else:
            print(
                "\n"
                "  New organizer:\n"
                f"    name:   {org_name}\n"
                f"    email:  {org_email}\n"
            )
            confirm = input("Is this correct? [N/y]: ").lower()
            if confirm in ['y', 'yes']:
                self.add_organizer = [org_name, org_email]
            else:
                self.add_new_organizer()

    def add_new_organizer(self):
        """Prompts the user through adding a new event organizer."""
        org_name = input("Organizer name? [none]: ") or None
        org_email = input("Organizer email? [none]: ") or None
        self.add_confirm_organizer(
                org_name,
                org_email)

    def archive(self, alias, force=False):
        """Archive an event identified by alias. Move the event to the
        {data_dir}/archive directory.

        Args:
            alias (str):    The alias of the event to be archived.
            force (bool):   Don't ask for confirmation before archiving.

        """
        archive_dir = os.path.join(self.data_dir, "archive")
        if not os.path.exists(archive_dir):
            try:
                os.makedirs(archive_dir)
            except OSError:
                msg = (
                    f"{archive_dir} doesn't exist and can't be created"
                )
                if not self.interactive:
                    self._error_exit(msg)
                else:
                    self._error_pass(msg)
                    return

        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            if force:
                confirm = "yes"
            else:
                confirm = input(f"Archive {alias}? [N/y]: ").lower()
            if confirm in ['yes', 'y']:
                filename = self.event_files.get(uid)
                if filename:
                    archive_file = os.path.join(
                        archive_dir, os.path.basename(filename))
                    try:
                        shutil.move(filename, archive_file)
                    except (IOError, OSError):
                        self._handle_error(f"failure moving {filename}")
                    else:
                        print(f"Archived event: {alias}")
                else:
                    self._handle_error(f"failed to find file for {alias}")
            else:
                print("Cancelled.")

    def attend(self, attendance):
        """Updates the attendance status for a meeting attendee.

        Args:
            attendance (list): the uid, identifier, and new status of
        attendee.

        Returns:
            opcode (str): op code for success or error.

        """
        uid = attendance[0]
        identifier = attendance[1]
        status = attendance[2].lower()
        opcode = "SUCCESS"
        if uid in self.events.keys():
            event = self.parse_event(uid)
            alias = event['alias']
            attendees = event['attendees']
            if attendees:
                matched = False
                for index, attendee in enumerate(attendees):
                    del_index = [index + 1]
                    this_name = attendee.get('name')
                    this_email = attendee.get('email')
                    # try to match on email address, fallback to name
                    if this_email:
                        if identifier in this_email:
                            self.modify(alias, del_attendee=del_index)
                            self.refresh()
                            self.modify(
                                alias,
                                add_attendee=[[
                                    this_name, this_email, status]])
                            self.refresh()
                            matched = True
                            break
                    elif this_name:
                        if identifier in this_name:
                            self.modify(alias, del_attendee=del_index)
                            self.refresh()
                            self.modify(
                                alias,
                                add_attendee=[[
                                    this_name, this_email, status]])
                            self.refresh()
                            matched = True
                            break
                if not matched:
                    # couldn't match an attendee
                    opcode = "NOMATCH"
            else:
                # event has no attendees
                opcode = "NOATTEND"
        else:
            # no such event
            opcode = "NOEVENT"
        return opcode

    def calc_next_recurrence(self, rrule, dt_start, dt_end):
        """Calculates the next recurrence for an event given start and
        end datetimes and a recurrence rule.

        Args:
            rrule (obj):        the recurrence rule object.
            dt_start (obj):     the start datetime.
            dt_end (obj):       the end datetime.

        Returns:
            next_start (obj):   the next start datetime.
            next_end (obj):     the next end datetime.

        """
        recurrences = self._calc_event_recurrences(rrule, dt_start)
        if recurrences:
            duration = dt_end - dt_start
            next_start = recurrences[0]
            next_end = next_start + duration
        else:
            next_start = None
            next_end = None

        return next_start, next_end

    def delete(self, alias, force=False):
        """Delete an event identified by alias.

        Args:
            alias (str):    The alias of the event to be deleted.

        """
        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            filename = self.event_files.get(uid)
            if filename:
                if force:
                    confirm = "yes"
                else:
                    confirm = input(f"Delete '{alias}'? [yes/no]: ").lower()
                if confirm in ['yes', 'y']:
                    try:
                        os.remove(filename)
                    except OSError:
                        self._handle_error(f"failure deleting {filename}")
                    else:
                        print(f"Deleted event: {alias}")
                else:
                    print("Cancelled")
            else:
                self._handle_error(f"failed to find file for {alias}")

    def edit(self, alias):
        """Edit an event identified by alias (using $EDITOR).

        Args:
            alias (str):    The alias of the event to be edited.

        """
        if self.editor:
            alias = alias.lower()
            uid = self._uid_from_alias(alias)
            if not uid:
                self._alias_not_found(alias)
            else:
                filename = self.event_files.get(uid)
                if filename:
                    try:
                        subprocess.run([self.editor, filename], check=True)
                    except subprocess.SubprocessError:
                        self._handle_error(
                            f"failure editing file {filename}")
                else:
                    self._handle_error(f"failed to find file for {alias}")
        else:
            self._handle_error("$EDITOR is required and not set")

    def edit_config(self):
        """Edit the config file (using $EDITOR) and then reload config."""
        if self.editor:
            try:
                subprocess.run(
                    [self.editor, self.config_file], check=True)
            except subprocess.SubprocessError:
                self._handle_error("failure editing config file")
            else:
                if self.interactive:
                    self._parse_config()
                    self.refresh()
        else:
            self._handle_error("$EDITOR is required and not set")

    def export(self, term, filename=None, invite=False):
        """Perform a search for events that match a given criteria and
        output the results in iCalendar VEVENT format.

        Args:
            term (str):     the criteria for which to search.
            filename (str): Optional. Filename to write iCalendar VEVENT
        output. This param is only useful in shell mode where
        redirection is not possible.
            invite (bool): Optional. The exported ICS is an invite.

        """
        def _export_wrap(text, length=75):
            """Wraps text that exceeds a given line length, with an
            indentation of one space on the next line.

            Args:
                text (str): the text to be wrapped.
                length (int): the maximum line length (default: 75).

            Returns:
                wrapped (str): the wrapped text.

            """
            wrapper = TextWrapper(
                width=length,
                subsequent_indent=' ',
                drop_whitespace=False,
                break_long_words=True)
            wrapped = '\r\n'.join(wrapper.wrap(text))
            return wrapped

        this_events = self.perform_search(term)

        if len(this_events) > 0:
            ical = (
                "BEGIN:VCALENDAR\r\n"
                "VERSION:2.0\r\n"
                f"PRODID:-//sdoconnell.net/{APP_NAME} {APP_VERS}//EN\r\n"
                "CALSCALE:GREGORIAN\r\n"
            )
            if invite:
                ical += "METHOD:REQUEST\r\n"
            for entry in this_events:
                uid = entry['uid']
                event = self.parse_event(uid)
                if event['created']:
                    created = self._export_timestamp(event['created'])
                else:
                    created = self._export_timestamp(
                            datetime.now(tz=self.ltz))
                if event['updated']:
                    updated = self._export_timestamp(event['updated'])
                else:
                    updated = self._export_timestamp(
                            datetime.now(tz=self.ltz))
                description = event['description']
                tags = event['tags']
                if tags:
                    tags = ','.join(tags).upper()
                rrule = event['rrule']
                notes = event['notes']
                attendees = event['attendees']
                reminders = event['reminders']
                start = event['start']
                end = event['end']
                location = event['location']
                organizer = event['organizer']
                if organizer:
                    org_name = organizer.get('name')
                    org_email = organizer.get('email')
                else:
                    org_name = None
                    org_email = None

                vevent = (
                    "BEGIN:VEVENT\r\n"
                    f"UID:{uid}\r\n"
                    f"DTSTAMP:{updated}\r\n"
                    f"CREATED:{created}\r\n"
                )
                if start:
                    start = self._export_timestamp(start)
                    vevent += f"DTSTART:{start}\r\n"
                if end:
                    end = self._export_timestamp(end)
                    vevent += f"DTEND:{end}\r\n"
                if description:
                    summarytxt = _export_wrap(f"SUMMARY:{description}")
                    vevent += f"{summarytxt}\r\n"
                if location:
                    location = location.replace(',', '\\,')
                    locationtxt = _export_wrap(f"LOCATION:{location}")
                    vevent += f"{locationtxt}\r\n"
                if tags:
                    categoriestxt = _export_wrap(f"CATEGORIES:{tags}")
                    vevent += f"{categoriestxt}\r\n"
                if rrule:
                    rdate = None
                    exdate = None
                    rrulekv = []
                    for key, value in rrule.items():
                        if key.lower() == "until" and value:
                            value = (self._datetime_or_none(value)
                                     .astimezone(timezone.utc)
                                     .strftime('%Y%m%dT%H%M%SZ'))
                            rrulekv.append(f"{key}={value}")
                        elif key.lower() == "date" and value:
                            rdate_dates = []
                            for datestr in value:
                                this_dt = self._datetime_or_none(datestr)
                                if this_dt:
                                    rdate_dates.append(
                                            self._export_timestamp(this_dt))
                            rdate = ','.join(rdate_dates)
                        elif key.lower() == "except" and value:
                            except_dates = []
                            for datestr in value:
                                this_dt = self._datetime_or_none(datestr)
                                if this_dt:
                                    except_dates.append(
                                            self._export_timestamp(this_dt))
                            exdate = ','.join(except_dates)
                        elif value:
                            rrulekv.append(f"{key}={value}")
                    rrulestr = ';'.join(rrulekv).upper()
                    rruletxt = _export_wrap(f"RRULE:{rrulestr}")
                    vevent += f"{rruletxt}\r\n"
                    if rdate:
                        rdatetxt = _export_wrap(f"RDATE:{rdate}")
                        vevent += f"{rdatetxt}\r\n"
                    if exdate:
                        exdatetxt = _export_wrap(f"EXDATE:{exdate}")
                        vevent += f"{exdatetxt}\r\n"

                if notes:
                    notes = notes.replace('\n', '\\n')
                    descriptiontxt = _export_wrap(f"DESCRIPTION:{notes}")
                    vevent += f"{descriptiontxt}\r\n"
                if reminders:
                    for reminder in reminders:
                        remind = reminder.get('remind')
                        notify = reminder.get('notify')
                        if remind:
                            remind = remind.upper()
                            vevent += "BEGIN:VALARM\r\n"
                            dt_trigger = self._datetime_or_none(remind)
                            if dt_trigger:
                                trigger = self._export_timestamp(dt_trigger)
                                vevent += (
                                    f"TRIGGER;VALUE=DATE-TIME:{trigger}\r\n")
                            elif remind.startswith("START-"):
                                trigger = remind.replace('START-', '-PT')
                                triggertxt = _export_wrap(
                                    f"TRIGGER:{trigger}")
                                vevent += f"{triggertxt}\r\n"
                            elif remind.startswith("START+"):
                                trigger = remind.replace('START+', 'PT')
                                triggertxt = _export_wrap(
                                    f"TRIGGER:{trigger}")
                                vevent += f"{triggertxt}\r\n"
                            elif remind.startswith("END-"):
                                trigger = remind.replace('END-', '-PT')
                                triggertxt = _export_wrap(
                                    f"TRIGGER;RELATED=END:{trigger}")
                                vevent += f"{triggertxt}\r\n"
                            elif remind.startswith("END+"):
                                trigger = remind.replace('END-', 'PT')
                                triggertxt = _export_wrap(
                                    f"TRIGGER;RELATED=END:{trigger}")
                                vevent += f"{triggertxt}\r\n"
                            if notify:
                                notify = notify.upper()
                                if notify not in ["DISPLAY", "EMAIL"]:
                                    notify = "DISPLAY"
                            else:
                                notify = "DISPLAY"
                            vevent += f"ACTION:{notify}\r\n"
                            if notify == "EMAIL" and self.user_email:
                                emailtxt = _export_wrap(
                                        f"ATTENDEE:mailto:{self.user_email}")
                                vevent += f"{emailtxt}\r\n"
                            vevent += "END:VALARM\n"
                if (attendees and (org_email or
                                   (self.user_name and self.user_email))):
                    if org_name and org_email:
                        organizertxt = _export_wrap(
                            f"ORGANIZER;CN={org_name}:"
                            f"mailto:{org_email}")
                        vevent += f"{organizertxt}\r\n"
                        # add the organizer as an ACCEPTED attendee
                        orgattendtxt = _export_wrap(
                            f"ATTENDEE;CUTYPE=INDIVIDUAL;"
                            f"ROLE=REQ-PARTICIPANT;"
                            f"PARTSTAT=ACCEPTED;RSVP=TRUE;"
                            f"CN={org_name}:mailto:"
                            f"{org_email}")
                    elif org_email:
                        organizertxt = _export_wrap(
                            f"ORGANIZER;CN={org_email}:"
                            f"mailto:{org_email}")
                        vevent += f"{organizertxt}\r\n"
                        # add the organizer as an ACCEPTED attendee
                        orgattendtxt = _export_wrap(
                            f"ATTENDEE;CUTYPE=INDIVIDUAL;"
                            f"ROLE=REQ-PARTICIPANT;"
                            f"PARTSTAT=ACCEPTED;RSVP=TRUE;"
                            f"CN={org_email}:mailto:"
                            f"{org_email}")
                    else:
                        organizertxt = _export_wrap(
                            f"ORGANIZER;CN={self.user_name}:"
                            f"mailto:{self.user_email}")
                        vevent += f"{organizertxt}\r\n"
                        # add the organizer as an ACCEPTED attendee
                        orgattendtxt = _export_wrap(
                            f"ATTENDEE;CUTYPE=INDIVIDUAL;"
                            f"ROLE=REQ-PARTICIPANT;"
                            f"PARTSTAT=ACCEPTED;RSVP=TRUE;"
                            f"CN={self.user_name}:mailto:"
                            f"{self.user_email}")
                    vevent += f"{orgattendtxt}\r\n"
                    # if there's no organizer, the user is the organizer
                    # but either way, an attendee has already been added,
                    # so we don't want to add another.
                    exclude_attend = org_email or self.user_email
                    for attendee in attendees:
                        name = attendee.get('name')
                        email = attendee.get('email')
                        status = attendee.get('status')
                        if email != exclude_attend:
                            if name and email:
                                if status:
                                    status = status.upper()
                                    if status not in [
                                            'ACCEPTED',
                                            'DECLINED',
                                            'TENTATIVE']:
                                        status = "NEEDS-ACTION"
                                else:
                                    status = "NEEDS-ACTION"
                                attendeetxt = _export_wrap(
                                    f"ATTENDEE;CUTYPE=INDIVIDUAL;"
                                    f"ROLE=REQ-PARTICIPANT;"
                                    f"PARTSTAT={status};RSVP=TRUE;"
                                    f"CN={name}:mailto:{email}")
                                vevent += f"{attendeetxt}\r\n"

                            elif email:
                                if status:
                                    status = status.upper()
                                    if status not in [
                                            'ACCEPTED',
                                            'DECLINED',
                                            'TENTATIVE']:
                                        status = "NEEDS-ACTION"
                                else:
                                    status = "NEEDS-ACTION"
                                attendeetxt = _export_wrap(
                                    f"ATTENDEE;CUTYPE=INDIVIDUAL;"
                                    f"ROLE=REQ-PARTICIPANT;"
                                    f"PARTSTAT={status};RSVP=TRUE;"
                                    f"CN={email}:mailto:{email}")
                                vevent += f"{attendeetxt}\r\n"

                vevent += "END:VEVENT\r\n"
                ical += vevent
            ical += "END:VCALENDAR\r\n"

            output = ical
        else:
            output = "No records found."
        if filename:
            filename = os.path.expandvars(os.path.expanduser(filename))
            try:
                with open(filename, "w",
                          encoding="utf-8") as ical_file:
                    ical_file.write(output)
            except (OSError, IOError):
                print("ERROR: unable to write iCalendar file.")
            else:
                print(f"iCalendar data written to {filename}.")
        else:
            print(output)

    def freebusy(self, interval, filename=None):
        """Gathers free/busy information for a given interval and
        outputs the results in iCalendar VFREEBUSY format.

        Args:
            interval (str): the free/busy interval for which to search.
            filename (str): Optional. Filename to write iCalendar
        VFREEBUSY output. This param is only useful in shell mode where
        redirection is not possible.

        """
        now = datetime.now(tz=timezone.utc)
        today = datetime.today().astimezone(tz=timezone.utc)
        rstart = today.replace(hour=0, minute=0, second=0, microsecond=0)
        rend = self._calc_relative_datetime(now, interval)
        output = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "CALSCALE:GREGORIAN\r\n"
            "BEGIN:VFREEBUSY\r\n"
            f"DTSTART:{self._export_timestamp(rstart)}\r\n"
            f"DTEND:{self._export_timestamp(rend)}\r\n"
            f"DTSTAMP:{self._export_timestamp(now)}\r\n"
        )

        for event in self.master_view:
            if rstart <= event['start'].astimezone(tz=timezone.utc) <= rend:
                start = self._export_timestamp(event['start'])
                end = self._export_timestamp(event['end'])
                output += f"FREEBUSY:{start}/{end}\r\n"
        output += (
            "END:VFREEBUSY\r\n"
            "END:VCALENDAR\r\n"
        )
        if filename:
            filename = os.path.expandvars(os.path.expanduser(filename))
            try:
                with open(filename, "w",
                          encoding="utf-8") as ical_file:
                    ical_file.write(output)
            except (OSError, IOError):
                print("ERROR: unable to write iCalendar file.")
            else:
                print(f"iCalendar data written to {filename}.")
        else:
            print(output)

    def info(self, alias, pager=False):
        """Display info about a specific event.

        Args:
            alias (str):    the event for which to provide info.
            pager (bool):   whether to page output.

        """
        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            event = self.parse_event(uid)

            console = Console()

            # description, start, end, tags
            summary_table = Table(
                title=f"Event info - {event['alias']}",
                title_style=self.style_title,
                title_justify="left",
                box=box.SIMPLE,
                show_header=False,
                show_lines=False,
                pad_edge=False,
                collapse_padding=False,
                padding=(0, 0, 0, 0))
            summary_table.add_column("field", style=self.style_label)
            summary_table.add_column("data")

            # calendar
            calendartxt = Text(event['calendar'])
            calendartxt.stylize(
                    self._make_calendar_style(event['calendar']))
            summary_table.add_row("calendar:", calendartxt)

            # description
            descriptiontxt = Text(event['description'])
            descriptiontxt.stylize(self.style_description)
            summary_table.add_row("description:", descriptiontxt)

            # location
            if event['location']:
                locationtxt = Text(event['location'])
                locationtxt.stylize(self.style_location)
                summary_table.add_row("location:", locationtxt)

            # tags
            if event['tags']:
                tagtxt = Text(','.join(event['tags']))
                tagtxt.stylize(self.style_tags)
                summary_table.add_row("tags:", tagtxt)

            if event['rrule']:
                rrule = event['rrule']
                rrulekv = []
                for key, value in rrule.items():
                    if key.lower() in ['date', 'except']:
                        pretty_dates = []
                        for item in value:
                            new_date = self._format_timestamp(
                                    item, pretty=True)
                            pretty_dates.append(new_date)
                        rrulekv.append(f"{key}={','.join(pretty_dates)}")
                    elif key.lower() == 'until':
                        value = self._format_timestamp(value, pretty=True)
                        rrulekv.append(f"{key}={value}")
                    elif value:
                        rrulekv.append(f"{key}={value}")
                rruletxt = Text(';'.join(rrulekv))
                next_start, next_end = self.calc_next_recurrence(
                        rrule, event['start'], event['end'])
                if not next_start:
                    next_start = event['start']
                if not next_end:
                    next_end = event['end']
            else:
                rruletxt = None
                next_start = event['start']
                next_end = event['end']

            # start
            startdate = Text(next_start.strftime("%Y-%m-%d"))
            startdate.stylize(self.style_date)
            starttime = Text(next_start.strftime("%H:%M"))
            starttime.stylize(self.style_time)
            starttxt = Text.assemble(startdate, " ", starttime)
            summary_table.add_row("start:", starttxt)

            # end
            enddate = Text(next_end.strftime("%Y-%m-%d"))
            enddate.stylize(self.style_date)
            endtime = Text(next_end.strftime("%H:%M"))
            endtime.stylize(self.style_time)
            endtxt = Text.assemble(enddate, " ", endtime)
            summary_table.add_row("end:", endtxt)

            # recurrence
            if rruletxt:
                summary_table.add_row("recurs:", rruletxt)

            # organizer
            if event['attendees']:
                if event['organizer']:
                    org_name = event['organizer'].get('name')
                    org_email = event['organizer'].get('email')
                    if org_name and org_email:
                        organizer = Text(f"{org_name} <{org_email}>")
                    elif org_name or org_email:
                        info_name = org_name or ""
                        info_email = org_email or ""
                        organizer = Text(f"{info_name}{info_email}")
                    else:
                        organizer = Text(
                                f"{self.user_name} <{self.user_email}>")
                else:
                    organizer = Text(f"{self.user_name} <{self.user_email}>")
                organizer.stylize(self.style_organizer)
                summary_table.add_row("organizer:", organizer)

            metadata_table = Table(
                title="Metadata",
                title_style=self.style_title,
                title_justify="left",
                box=box.SIMPLE,
                show_header=False,
                show_lines=False,
                pad_edge=False,
                collapse_padding=False,
                padding=(0, 0, 0, 0))
            metadata_table.add_column("field", style=self.style_label)
            metadata_table.add_column("data")
            created_txt = Text(event['created'].strftime("%Y-%m-%d %H:%M"))
            created_txt.stylize(self.style_date)
            metadata_table.add_row("created:", created_txt)
            updated_txt = Text(event['updated'].strftime("%Y-%m-%d %H:%M"))
            updated_txt.stylize(self.style_date)
            metadata_table.add_row("updated:", updated_txt)
            metadata_table.add_row("uid:", uid)

            # reminders
            if event['reminders']:
                reminder_table = Table(
                    title="Reminders",
                    title_style=self.style_title,
                    title_justify="left",
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    pad_edge=False,
                    collapse_padding=False,
                    padding=(0, 0, 0, 0))
                reminder_table.add_column("entry")

                for index, reminder in enumerate(event['reminders']):
                    remind = self._calc_reminder(
                            reminder.get('remind'),
                            next_start,
                            next_end)
                    if remind:
                        notify = reminder.get('notify')
                        if not notify:
                            notify = " (display)"
                        else:
                            notify = f" ({notify})"
                        remindstr = remind.strftime("%Y-%m-%d %H:%M")
                        notifytxt = Text(f"[{index + 1}] {remindstr}{notify}")
                        reminder_table.add_row(notifytxt)

            # attendees
            if event['attendees']:
                attendee_table = Table(
                    title="Attendees",
                    title_style=self.style_title,
                    title_justify="left",
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    pad_edge=False,
                    collapse_padding=False,
                    padding=(0, 0, 0, 0))
                attendee_table.add_column("entry")

                for index, attendee in enumerate(event['attendees']):
                    name = attendee.get('name')
                    if name:
                        email = attendee.get('email')
                        if not email:
                            email = ""
                        else:
                            email = f" <{email}>"
                        status = attendee.get('status')
                        if not status:
                            status = " [none]"
                        else:
                            status = f" [{status.lower()}]"
                        attendeetxt = Text(
                            f"[{index + 1}] {name}{email}{status}")
                        attendee_table.add_row(attendeetxt)

            # attachments
            if event['attachments']:
                attachment_table = Table(
                    title="Attachments",
                    title_style=self.style_title,
                    title_justify="left",
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    pad_edge=False,
                    collapse_padding=False,
                    padding=(0, 0, 0, 0))
                attachment_table.add_column("entry")

                for index, attachment in enumerate(event['attachments']):
                    attachmenttxt = Text(f"[{index + 1}] {attachment}")
                    attachment_table.add_row(attachmenttxt)

            # history (for recurring events)
            if event['rrule']:
                history_table = Table(
                    title="History",
                    title_style=self.style_title,
                    title_justify="left",
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    pad_edge=False,
                    collapse_padding=False,
                    padding=(0, 0, 0, 0))
                history_table.add_column("entry")

                prior_occurences = self._calc_event_recurrences(
                        event['rrule'], event['start'], past=True)
                if prior_occurences:
                    for occurence in prior_occurences:
                        if occurence < datetime.now(tz=self.ltz):
                            occurencestr = self._format_timestamp(
                                occurence, pretty=True)
                            occurencetxt = Text(f"- {occurencestr}")
                            history_table.add_row(occurencetxt)

            # notes
            if event['notes']:
                notes_table = Table(
                    title="Notes",
                    title_style=self.style_title,
                    title_justify="left",
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    pad_edge=False,
                    collapse_padding=False,
                    padding=(0, 0, 0, 0))
                notes_table.add_column("entry")
                notes_table.add_row(Text(event['notes']))

            layout = Table.grid()
            layout.add_column("single")
            layout.add_row("")
            layout.add_row(summary_table)
            layout.add_row(metadata_table)
            if 'reminder_table' in locals():
                layout.add_row(reminder_table)
            if 'attendee_table' in locals():
                layout.add_row(attendee_table)
            if 'attachment_table' in locals():
                layout.add_row(attachment_table)
            if 'notes_table' in locals():
                layout.add_row(notes_table)
            if 'history_table' in locals():
                layout.add_row(history_table)

            # render the output with a pager if --pager or -p
            if pager:
                if self.color_pager:
                    with console.pager(styles=True):
                        console.print(layout)
                else:
                    with console.pager():
                        console.print(layout)
            else:
                console.print(layout)

    def invite(self, alias):
        """Sends meeting invitations to all attendees of an event.

        Args:
            alias (str): the event for which to send invitations.

        """
        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            event = self.parse_event(uid)
            attendees = event['attendees']
            if attendees:
                subject = f"\"Invitation: {event['description']}\""
                recipients = []
                for attendee in attendees:
                    email = attendee.get('email')
                    if email:
                        recipients.append(email)
                if len(recipients) > 0:
                    tempdir = tempfile.gettempdir()
                    ics_file = os.path.join(tempdir, 'invite.ics')
                    term = f"alias={alias}"
                    self.export(term, filename=ics_file, invite=True)
                    for recipient in recipients:
                        raw_cmd = self.mailer_cmd.split()
                        # this could probably be done with list comp
                        # but might be more confusing than a simple loop
                        this_mailer_cmd = []
                        for item in raw_cmd:
                            if item == '%s':
                                this_mailer_cmd.append(subject)
                            elif item == '%a':
                                this_mailer_cmd.append(ics_file)
                            elif item == '%b':
                                this_mailer_cmd.append("Invitation")
                            elif item == '%r':
                                this_mailer_cmd.append(recipient)
                            else:
                                this_mailer_cmd.append(item)
                        this_mailer_cmd = " ".join(this_mailer_cmd)
                        invite = subprocess.run(
                            this_mailer_cmd,
                            capture_output=True,
                            check=True,
                            shell=True)
                        result = invite.returncode
                        if result != 0:
                            print(f"Failure sending invite to {recipient}.")
                        else:
                            print(f"Sent invite to {recipient}.")
                    os.remove(ics_file)
            else:
                self._handle_error(f"no attendees listed on {alias}")

    def list(
            self,
            view,
            start=None,
            end=None,
            pager=None,
            cal_filter=None):
        """Prints a list of events within a view.

        Args:
            view (str):     the calendar view (today, tomorrow, yesterday,
        thisweek, nextweek, month, year, or custom)
            start (str):    datetime-like string for start day/time.
            end (str):      datetime-like string for end day/time.
            pager (bool):   paginate output.
            cal_filter (str): filter events to a specific calendar.

        """
        def _occurence_data(entry, event):
            """Combines data from two dicts - entry and event, and
            returns a dict including all fields needed to format a
            calendar entry.

            Args:

                entry (dict):   data for an occurence from the master
            view.
                event (dict):   data for the event itself.

            Returns:

                data (dict):    the combined data structure.

            """
            data = {}
            data['start'] = entry['start']
            data['end'] = entry['end']
            data['alias'] = event['alias']
            data['calendar'] = event['calendar']
            data['description'] = event['description']
            data['location'] = event['location']
            data['tags'] = event['tags']
            data['notes'] = event['notes']
            data['rrule'] = event['rrule']

            return data

        startstr = start
        endstr = end
        start = self._datetime_or_none(start)
        end = self._datetime_or_none(end)
        if end:
            if end.strftime("%H:%M:%S") == "00:00:00":
                end = end + timedelta(hours=23, minutes=59, seconds=59)
        view = view.lower()
        if cal_filter:
            cal_filter = cal_filter.lower()
        now = datetime.now(tz=self.ltz)
        cal = modcalendar.Calendar(firstweekday=self.first_weekday)
        today = date.today()
        today_wd = today.weekday()
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)
        this_year = today.year
        next_year = this_year + 1
        last_year = this_year - 1
        this_month = today.month
        this_month_ld = modcalendar.monthrange(this_year, this_month)[1]
        next_month = this_month + 1
        if next_month == 13:
            next_month = 1
            nm_year = this_year + 1
        else:
            nm_year = this_year
        next_month_ld = modcalendar.monthrange(nm_year, next_month)[1]
        last_month = this_month - 1
        if last_month == 0:
            last_month = 12
            lm_year = this_year - 1
        else:
            lm_year = this_year
        last_month_ld = modcalendar.monthrange(lm_year, last_month)[1]
        this_week_start = today - timedelta(
                days=list(cal.iterweekdays()).index(today_wd))
        this_week_end = this_week_start + timedelta(days=6)
        last_week_start = this_week_start - timedelta(days=7)
        last_week_end = last_week_start + timedelta(days=6)
        next_week_start = this_week_start + timedelta(days=7)
        next_week_end = next_week_start + timedelta(days=6)
        if view == "agenda":
            selected_events = []
            for entry in self.master_view:
                if entry['start'].date() == today and entry['start'] >= now:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    view,
                    pager=pager,
                    cal_filter=cal_filter)
        elif view == "today":
            selected_events = []
            for entry in self.master_view:
                if entry['start'].date() == today:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    view,
                    pager=pager,
                    cal_filter=cal_filter)
        elif view == "tomorrow":
            selected_events = []
            for entry in self.master_view:
                if entry['start'].date() == tomorrow:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    view,
                    pager=pager,
                    cal_filter=cal_filter)
        elif view == "yesterday":
            selected_events = []
            for entry in self.master_view:
                if entry['start'].date() == yesterday:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    view,
                    pager=pager,
                    cal_filter=cal_filter)
        elif view == "thisweek":
            selected_events = []
            for entry in self.master_view:
                if this_week_start <= entry['start'].date() <= this_week_end:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                selected_events,
                "this week",
                pager=pager,
                weekstart=this_week_start,
                cal_filter=cal_filter)
        elif view == "nextweek":
            selected_events = []
            for entry in self.master_view:
                if next_week_start <= entry['start'].date() <= next_week_end:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    "next week",
                    pager=pager,
                    weekstart=next_week_start,
                    cal_filter=cal_filter)
        elif view == "lastweek":
            selected_events = []
            for entry in self.master_view:
                if last_week_start <= entry['start'].date() <= last_week_end:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    "last week",
                    pager=pager,
                    weekstart=last_week_start,
                    cal_filter=cal_filter)
        elif view == "thismonth":
            selected_events = []
            this_month_start = date(this_year, this_month, 1)
            this_month_end = date(this_year, this_month, this_month_ld)
            for entry in self.master_view:
                if this_month_start <= entry['start'].date() <= this_month_end:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    "this month",
                    pager=pager,
                    month=this_month,
                    year=this_year,
                    cal_filter=cal_filter)
        elif view == "nextmonth":
            selected_events = []
            next_month_start = date(nm_year, next_month, 1)
            next_month_end = date(nm_year, next_month, next_month_ld)
            for entry in self.master_view:
                if next_month_start <= entry['start'].date() <= next_month_end:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    "next month",
                    pager=pager,
                    month=next_month,
                    year=nm_year,
                    cal_filter=cal_filter)
        elif view == "lastmonth":
            selected_events = []
            last_month_start = date(lm_year, last_month, 1)
            last_month_end = date(lm_year, last_month, last_month_ld)
            for entry in self.master_view:
                if last_month_start <= entry['start'].date() <= last_month_end:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    "last month",
                    pager=pager,
                    month=last_month,
                    year=lm_year,
                    cal_filter=cal_filter)
        elif view == "thisyear":
            selected_events = []
            this_year_start = date(this_year, 1, 1)
            this_year_end = date(this_year, 12, 31)
            for entry in self.master_view:
                if this_year_start <= entry['start'].date() <= this_year_end:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    "this year",
                    pager=pager,
                    year=this_year,
                    cal_filter=cal_filter)
        elif view == "nextyear":
            selected_events = []
            next_year_start = date(next_year, 1, 1)
            next_year_end = date(next_year, 12, 31)
            for entry in self.master_view:
                if next_year_start <= entry['start'].date() <= next_year_end:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    "next year",
                    pager=pager,
                    year=next_year,
                    cal_filter=cal_filter)
        elif view == "lastyear":
            selected_events = []
            last_year_start = date(last_year, 1, 1)
            last_year_end = date(last_year, 12, 31)
            for entry in self.master_view:
                if last_year_start <= entry['start'].date() <= last_year_end:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    "last year",
                    pager=pager,
                    year=last_year,
                    cal_filter=cal_filter)
        elif view == "custom" and start and end:
            selected_events = []
            for entry in self.master_view:
                if start <= entry['start'] <= end:
                    event = self.parse_event(entry['uid'])
                    add_event = True
                    if cal_filter:
                        if cal_filter != event['calendar']:
                            add_event = False
                    if add_event:
                        e_data = _occurence_data(entry, event)
                        selected_events.append(e_data)
            self._print_event_list(
                    selected_events,
                    f"custom\n[{startstr} - {endstr}]",
                    pager=pager,
                    cal_filter=cal_filter)
        else:
            selected_events = []
            for uid in self.events:
                if view == self.events[uid]['alias'].lower():
                    event = self.parse_event(uid)
                    if event['rrule']:
                        start, end = self.calc_next_recurrence(
                            event['rrule'], event['start'], event['end'])
                    else:
                        start = event['start']
                        end = event['end']
                    entry = {
                        'uid': uid,
                        'start': start,
                        'end': end
                    }
                    e_data = _occurence_data(entry, event)
                    selected_events.append(e_data)
            if selected_events:
                self._print_event_list(
                    selected_events,
                    view,
                    pager=pager)
            else:
                self._handle_error(
                    "invalid view name, alias, or custom date/time range")

    def modify(
            self,
            alias,
            new_calendar=None,
            new_description=None,
            new_location=None,
            new_tags=None,
            new_start=None,
            new_end=None,
            new_rrule=None,
            new_organizer=None,
            add_reminder=None,
            del_reminder=None,
            add_attendee=None,
            del_attendee=None,
            add_attachment=None,
            del_attachment=None,
            new_notes=None):
        """Modify an event using provided parameters.

        Args:
            alias (str):            event alias being updated.
            new_calendar (str):     event calendar.
            new_description (str):  event description.
            new_location (str):     event location.
            new_tags (str):         tags assigned to the event.
            new_start (str):        event start date ("%Y-%m-%d[ %H:%M]").
            new_end (str):          event end date ("%Y-%m-%d[ %H:%M]")
            or expression (x)d(y)h(z)m.
            new_rrule (str):        event recurrence rule.
            new_organizer (list):   event organizer name, email
            add_reminder (list):    new event reminder(s).
            del_reminder (int):     reminder index number.
            add_attendee (list):    new event attendee(s).
            del_attendee (int):     attendee index number.
            add_attachment (list):  new event attachment(s).
            del_attachment (int):   attachment index number.
            new_notes (str):        notes assigned to the event.

        """
        def _remove_items(deletions, source):
            """Removes items (identified by index) from a list.

            Args:
                deletions (list):   the indexes to be deleted.
                source (list):    the list from which to remove.

            Returns:
                source (list):    the modified list.

            """
            rem_items = []
            for entry in deletions:
                try:
                    entry = int(entry)
                except ValueError:
                    pass
                else:
                    if 1 <= entry <= len(source):
                        entry -= 1
                        rem_items.append(source[entry])
            if rem_items:
                for item in rem_items:
                    source.remove(item)
            return source

        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            filename = self.event_files.get(uid)
            event = self.parse_event(uid)

            if filename:
                created = event['created']
                u_updated = datetime.now(tz=self.ltz)
                if not new_start:
                    u_start = event['start']
                if not new_end:
                    u_end = event['end']

                if new_start and new_end:
                    u_start = self._datetime_or_none(new_start)
                    if not u_start:
                        u_start = event['start']
                    u_end = self._calc_end_dt(u_start, new_end)
                    if not self._validate_start_end(u_start, u_end):
                        msg = "event 'end' must be AFTER event 'start'"
                        if self.interactive:
                            self._error_pass(msg)
                            return
                        else:
                            self._error_exit(msg)
                elif new_start:
                    u_start = self._datetime_or_none(new_start)
                    if not u_start:
                        u_start = event['start']
                    else:
                        # keep the original event duration
                        duration = event['end'] - event['start']
                        u_end = u_start + duration
                elif new_end:
                    u_end = self._calc_end_dt(u_start, new_end)
                    if not self._validate_start_end(u_start, u_end):
                        msg = "event 'end' must be AFTER event 'start'"
                        if self.interactive:
                            self._error_pass(msg)
                            return
                        else:
                            self._error_exit(msg)

                u_calendar = new_calendar or event['calendar']
                u_description = new_description or event['description']
                u_location = new_location or event['location']

                if new_organizer:
                    if len(new_organizer) > 1:
                        org_name = new_organizer[0]
                        org_email = new_organizer[1]
                    else:
                        org_name = None
                        org_email = new_organizer[0]
                    new_organizer = {}
                    new_organizer['name'] = org_name
                    new_organizer['email'] = org_email
                u_organizer = new_organizer or event['organizer']

                if new_tags:
                    new_tags = new_tags.lower()
                    if new_tags.startswith('+'):
                        new_tags = new_tags[1:]
                        new_tags = new_tags.split(',')
                        tags = [] if not event['tags'] else event['tags'].copy()
                        for new_tag in new_tags:
                            if new_tag not in tags:
                                tags.append(new_tag)
                        if tags:
                            tags.sort()
                            u_tags = tags
                        else:
                            u_tags = None
                    elif new_tags.startswith('~'):
                        new_tags = new_tags[1:]
                        new_tags = new_tags.split(',')
                        if event['tags']:
                            tags = event['tags'].copy()
                            for new_tag in new_tags:
                                if new_tag in tags:
                                    tags.remove(new_tag)
                            if tags:
                                tags.sort()
                                u_tags = tags
                            else:
                                u_tags = None
                        else:
                            u_tags = None
                    else:
                        u_tags = new_tags.split(',')
                        u_tags.sort()
                else:
                    u_tags = event['tags']

                if new_rrule:
                    u_rrule = self.parse_rrule(new_rrule)
                else:
                    u_rrule = event['rrule']

                if add_reminder or del_reminder:
                    u_reminders = (
                        [] if not event['reminders']
                        else event['reminders'].copy()
                    )
                    if del_reminder and u_reminders:
                        u_reminders = _remove_items(del_reminder,
                                                    u_reminders)
                    if add_reminder:
                        for a_rem in add_reminder:
                            rem_data = {}
                            if len(a_rem) > 0:
                                rem_data['remind'] = a_rem[0]
                                if len(a_rem) == 2:
                                    remtype = str(a_rem[1]).lower()
                                    if remtype in ['display', 'email']:
                                        rem_data['notify'] = remtype
                                    else:
                                        rem_data['notify'] = 'display'
                                u_reminders.append(rem_data)
                else:
                    u_reminders = event['reminders']

                if add_attendee or del_attendee:
                    u_attendees = (
                        [] if not event['attendees']
                        else event['attendees'].copy()
                    )
                    if del_attendee and u_attendees:
                        u_attendees = _remove_items(del_attendee,
                                                    u_attendees)
                    if add_attendee:
                        for a_att in add_attendee:
                            att_data = {}
                            if len(a_att) > 0:
                                att_data['name'] = a_att[0]
                                if len(a_att) >= 2:
                                    att_data['email'] = a_att[1]
                                if len(a_att) == 3:
                                    att_data['status'] = a_att[2].lower()
                                u_attendees.append(att_data)
                else:
                    u_attendees = event['attendees']

                if add_attachment or del_attachment:
                    u_attachments = (
                        [] if not event['attachments']
                        else event['attachments'].copy()
                    )
                    if del_attachment and u_attachments:
                        u_attachments = _remove_items(del_attachment,
                                                      u_attachments)
                    if add_attachment:
                        for a_atc in add_attachment:
                            u_attachments.append(a_atc)
                else:
                    u_attachments = event['attachments']

                # notes
                if new_notes:
                    # the new note is functionally empty or is using a
                    # placeholder from notes() to clear the notes
                    if new_notes in [' ', ' \n', '\n']:
                        u_notes = None
                    else:
                        u_notes = new_notes
                else:
                    u_notes = event['notes']

                data = {
                    "event": {
                        "uid": uid,
                        "created": created,
                        "updated": u_updated,
                        "alias": alias,
                        "calendar": u_calendar,
                        "description": u_description,
                        "location": u_location,
                        "tags": u_tags,
                        "start": u_start,
                        "end": u_end,
                        "reminders": u_reminders,
                        "rrule": u_rrule,
                        "organizer": u_organizer,
                        "attendees": u_attendees,
                        "attachments": u_attachments,
                        "notes": u_notes
                    }
                }
                # write the updated file
                self._write_yaml_file(data, filename)

    def new(
            self,
            calendar=None,
            description=None,
            location=None,
            tags=None,
            start=None,
            end=None,
            reminders=None,
            rrule=None,
            organizer=None,
            attendees=None,
            attachments=None,
            notes=None):
        """Create a new event.

        Args:
            calendar (str):     event calendar.
            description (str):  event description.
            location (str):     event location.
            tags (str):         tags assigned to the event.
            start (str):        event start datetime ("%Y-%m-%d[ %H:%M]").
            end (str):          event end datetime ("%Y-%m-%d[ %H:%M]")
            or expression (x)d(y)h(z)m.
            reminders (list):   event reminder expressions.
            rrule (str):        event recurring rule expression.
            organizer (list):   event organizer name, email
            attendees (list):   event attendees.
            attachments (list): event attached files.
            notes (str):        notes assigned to the event.

        """
        uid = str(uuid.uuid4())
        now = datetime.now(tz=self.ltz)
        created = now
        updated = now
        alias = self._gen_alias()
        calendar = calendar or "default"
        if calendar:
            calendar = calendar.lower()
        description = description or "New event"
        if organizer:
            if len(organizer) > 1:
                org_name = organizer[0]
                org_email = organizer[1]
            else:
                org_name = None
                org_email = organizer[0]
            new_organizer = {}
            new_organizer['name'] = org_name
            new_organizer['email'] = org_email
        else:
            new_organizer = None
        if tags:
            tags = tags.lower()
            tags = tags.split(',')
            tags.sort()
        if start:
            dt_start = self._datetime_or_none(start)
        if not dt_start:
            msg = "event requires a start date[time]"
            if self.interactive:
                self._error_pass(msg)
                return
            else:
                self._error_exit(msg)
        if end:
            dt_end = self._calc_end_dt(dt_start, end)
            if not self._validate_start_end(dt_start, dt_end):
                msg = "event end must be AFTER event start"
                if self.interactive:
                    self._error_pass(msg)
                    return
                else:
                    self._error_exit(msg)
        else:
            # default event duration
            dt_end = dt_start + timedelta(
                    minutes=self.default_duration)

        if reminders:
            new_reminders = []
            for entry in reminders:
                rem_data = {}
                if len(entry) > 0:
                    rem_data['remind'] = entry[0]
                    if len(entry) == 2:
                        remtype = str(entry[1]).lower()
                        if remtype in ['display', 'email']:
                            rem_data['notify'] = remtype
                        else:
                            rem_data['notify'] = 'display'
                    new_reminders.append(rem_data)
        else:
            new_reminders = None

        if rrule:
            new_rrule = self.parse_rrule(rrule)
        else:
            new_rrule = None

        if attendees:
            if new_organizer:
                exclude_attend = new_organizer.get('email')
            else:
                exclude_attend = None
            new_attendees = []
            for entry in attendees:
                att_data = {}
                if len(entry) > 0:
                    if len(entry) == 1:
                        att_data['email'] = entry[0]
                    if len(entry) == 2:
                        att_data['email'] = entry[0]
                        att_data['status'] = entry[1].lower()
                    if len(entry) > 2:
                        att_data['name'] = entry[0]
                        att_data['email'] = entry[1]
                        att_data['status'] = entry[2].lower()
                    if att_data['email'] != exclude_attend:
                        new_attendees.append(att_data)
        else:
            new_attendees = None

        filename = os.path.join(self.data_dir, f'{uid}.yml')
        data = {
            "event": {
                "uid": uid,
                "created": created,
                "updated": updated,
                "alias": alias,
                "calendar": calendar,
                "description": description,
                "location": location,
                "tags": tags,
                "start": dt_start,
                "end": dt_end,
                "reminders": new_reminders,
                "rrule": new_rrule,
                "organizer": new_organizer,
                "attendees": new_attendees,
                "attachments": attachments,
                "notes": notes
            }
        }
        # write the updated file
        self._write_yaml_file(data, filename)
        print(f"Added event: {alias}")

    def new_event_wizard(self):
        """Prompt the user for event parameters and then call new()."""
        def _ask_start():
            """Asks for an start time for a new event and checks for
            valid datetime information.

            Returns:
                start_dt (str):    datetime representing the event start.

            """
            start = input("Start date/time [none]: ")
            start_dt = self._datetime_or_none(start)
            while not start_dt:
                self._error_pass(
                        "Start date/time empty or invalid "
                        "(try: %Y-%m-%d [%H:%M])")
                start_dt = _ask_start()
            return start_dt

        def _ask_end(start):
            """Asks for an end time or duration for a new event and
            checks for valid input.

            Args:
                start (str): datetime representing the event start.

            Returns:
                end (str):  datetime representing the event end.

            """
            end = input("End date/time or duration? [default]: ")
            if not end:
                end_dt = self._calc_relative_datetime(
                        start, self.default_duration)
            else:
                end_dt = self._datetime_or_none(end)
                if not end_dt:
                    end_dt = self._calc_relative_datetime(
                            start, end)
            start_dt = self._datetime_or_none(start)
            while end_dt < start_dt:
                self._error_pass(
                        "End date/time must be after start")
                end_dt = _ask_end(start)
            return end_dt

        calendar = input("Add to calendar [default]: ") or 'default'
        description = input("Description [New event]: ") or 'New event'
        location = input("Location [none]: ") or None
        start = _ask_start()
        end = _ask_end(start)
        tags = input("Tags [none]: ") or None
        # reminders, attendees, attachments, recurrence rule
        other = input("Other options? [N/y]: ").lower()
        if other in ['y', 'yes']:
            add_reminder = input("Add reminder? [N/y]: ").lower()
            if add_reminder in ['y', 'yes']:
                self.add_new_reminder()
            else:
                self.add_reminders = None

            add_attendee = input("Add attendee? [N/y]: ").lower()
            if add_attendee in ['y', 'yes']:
                self.add_new_attendee()
            else:
                self.add_attendees = None

            add_organizer = input(
                "Add an organizer (other than yourself)? [N/y]: ").lower()
            if add_organizer in ['y', 'yes']:
                self.add_new_organizer()
            else:
                self.add_organizer = None

            add_attachment = input("Add attachment? [N/y]: ").lower()
            if add_attachment in ['y', 'yes']:
                self.add_new_attachment()
            else:
                self.add_attachments = None

            rrule = input("Recurrence rule? [none]: ").lower() or None
        else:
            self.add_reminders = None
            self.add_attendees = None
            self.add_organizer = None
            self.add_attachments = None
            rrule = None

        self.new(
            calendar=calendar,
            description=description,
            location=location,
            tags=tags,
            start=start,
            end=end,
            reminders=self.add_reminders,
            rrule=rrule,
            organizer=self.add_organizer,
            attendees=self.add_attendees,
            attachments=self.add_attachments,
            notes=None)

        # reset
        self.add_reminders = None
        self.add_attendees = None
        self.add_organizer = None
        self.add_attachments = None

    def notes(self, alias):
        """Add or update notes on an event.

        Args:
            alias (str):        the event alias being updated.

        """
        if self.editor:
            alias = alias.lower()
            uid = self._uid_from_alias(alias)
            if not uid:
                self._alias_not_found(alias)
            else:
                event = self.parse_event(uid)
                if not event['notes']:
                    fnotes = ""
                else:
                    fnotes = event['notes']
                handle, abs_path = tempfile.mkstemp()
                with os.fdopen(handle, 'w') as temp_file:
                    temp_file.write(fnotes)

                # open the tempfile in $EDITOR and then update the event
                # with the new note
                try:
                    subprocess.run([self.editor, abs_path], check=True)
                    with open(abs_path, "r",
                              encoding="utf-8") as temp_file:
                        new_note = temp_file.read()
                except subprocess.SubprocessError:
                    msg = "failure editing note"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
                else:
                    # notes were deleted entirely but if we set this to
                    # None then the note won't be updated. Set it to " "
                    # and then use special handling in modify()
                    if event['notes'] and not new_note:
                        new_note = " "
                    self.modify(
                        alias=alias,
                        new_notes=new_note)
                    os.remove(abs_path)
        else:
            self._handle_error("$EDITOR is required and not set")

    def parse_event(self, uid):
        """Parse an event and return values for event parameters.

        Args:
            uid (str): the UUID of the event to parse.

        Returns:
            event (dict):    the event parameters.

        """
        event = {}
        event['uid'] = self.events[uid].get('uid')

        event['created'] = self.events[uid].get('created')
        if event['created']:
            event['created'] = self._datetime_or_none(event['created'])

        event['updated'] = self.events[uid].get('updated')
        if event['updated']:
            event['updated'] = self._datetime_or_none(event['updated'])

        event['alias'] = self.events[uid].get('alias')
        if event['alias']:
            event['alias'] = event['alias'].lower()

        event['calendar'] = self.events[uid].get('calendar', 'default')
        if event['calendar']:
            event['calendar'] = event['calendar'].lower()

        event['rrule'] = self.events[uid].get('rrule')

        event['start'] = self.events[uid].get('start')
        if event['start']:
            event['start'] = self._datetime_or_none(event['start'])
        # failsafe
        if not event['start']:
            event['start'] = datetime.now(tz=self.ltz)

        event['end'] = self.events[uid].get('end')
        if event['end']:
            event['end'] = self._datetime_or_none(event['end'])
        # failsafe
        if not event['end']:
            event['end'] = self._calc_end_dt(event['start'], None)

        event['description'] = self.events[uid].get('description')
        event['location'] = self.events[uid].get('location')
        event['tags'] = self.events[uid].get('tags')
        event['reminders'] = self.events[uid].get('reminders')
        event['organizer'] = self.events[uid].get('organizer')
        event['attendees'] = self.events[uid].get('attendees')
        event['attachments'] = self.events[uid].get('attachments')
        event['notes'] = self.events[uid].get('notes')

        return event

    def parse_rrule(self, expression):
        """Parses a recurring rule expression and returns a dict of
        recurrence parameters.

        Args:
            expression (str):   the rrule expression.

        Returns:
            rrule (dict):       the recurrence parameters (or None)

        """
        expression = expression.lower()
        valid_criteria = [
                "date=",        # specific recurrence dates
                "except=",      # specific exception dates
                "freq=",        # frequency (minutely, hourly, daily,
                                #   weekly, monthly, yearly)
                "count=",       # number of recurrences
                "until=",       # recur until date
                "interval=",    # interval of recurrence
                "byhour=",      # recur by hour (0-23)
                "byweekday=",   # SU, MO, TU, WE, TH, FR, SA
                "bymonth=",     # recur by month (1-12)
                "bymonthday=",  # day of month (1-31)
                "byyearday=",   # day of the year (1-366)
                "byweekno=",    # week of year (1-53)
                "bysetpos=",    # set position of occurence set (e.g.,
                                # 1 for first, -1 for last, -2 for
                                # second to last
        ]
        if not any(x in expression for x in valid_criteria):
            rrule = None
        else:
            try:
                rrule = dict((k.strip(), v.strip())
                             for k, v in (item.split('=')
                             for item in expression.split(';')))
            except ValueError:
                rrule = None

        if rrule.get('date'):
            date_strings = rrule['date'].split(',')
            rr_date = []
            for entry in date_strings:
                this_date = self._datetime_or_none(entry)
                if this_date:
                    rr_date.append(this_date)
            rrule['date'] = sorted(rr_date)

        if rrule.get('except'):
            except_strings = rrule['except'].split(',')
            rr_except = []
            for entry in except_strings:
                this_except = self._datetime_or_none(entry)
                if this_except:
                    rr_except.append(this_except)
            rrule['except'] = sorted(rr_except)

        if rrule.get('freq'):
            rr_freq = rrule['freq'].upper()
            if rr_freq in ['MINUTELY', 'HOURLY', 'DAILY',
                           'WEEKLY', 'MONTHLY', 'YEARLY']:
                rrule['freq'] = rr_freq
            else:
                rrule['freq'] = None

        if rrule.get('count'):
            rrule['count'] = self._integer_or_default(rrule['count'])

        if rrule.get('until'):
            rrule['until'] = self._datetime_or_none(rrule['until'])

        if rrule.get('interval'):
            rrule['interval'] = self._integer_or_default(rrule['interval'])

        if rrule.get('byhour'):
            rr_byhour = self._integer_or_default(rrule['byhour'])
            if rr_byhour:
                if 0 <= rr_byhour <= 23:
                    rrule['byhour'] = rr_byhour
                else:
                    rrule['byhour'] = None
            else:
                rrule['byhour'] = None

        if rrule.get('byweekday'):
            rr_byweekday = rrule['byweekday'].upper()
            if rr_byweekday in ['SU', 'MO', 'TU', 'WE',
                                'TH', 'FR', 'SA']:
                rrule['byweekday'] = rr_byweekday
            else:
                rrule['byweekday'] = None

        if rrule.get('bymonth'):
            rr_bymonth = self._integer_or_default(rrule['bymonth'])
            if rr_bymonth:
                if 1 <= rr_bymonth <= 12:
                    rrule['bymonth'] = rr_bymonth
                else:
                    rrule['bymonth'] = None
            else:
                rrule['bymonth'] = None

        if rrule.get('bymonthday'):
            rr_bymonthday = self._integer_or_default(rrule['bymonthday'])
            if rr_bymonthday:
                if 1 <= rr_bymonthday <= 31:
                    rrule['bymonthday'] = rr_bymonthday
                else:
                    rrule['bymonthday'] = None
            else:
                rrule['bymonthday'] = None

        if rrule.get('byyearday'):
            rr_byyearday = self._integer_or_default(rrule['byyearday'])
            if rr_byyearday:
                if 1 <= rr_byyearday <= 366:
                    rrule['byyearday'] = rr_byyearday
                else:
                    rrule['byyearday'] = None
            else:
                rrule['byyearday'] = None

        if rrule.get('byweekno'):
            rr_byweekno = self._integer_or_default(rrule['byweekno'])
            if rr_byweekno:
                if 1 <= rr_byweekno <= 53:
                    rrule['byweekno'] = rr_byweekno
                else:
                    rrule['byweekno'] = None
            else:
                rrule['byweekno'] = None

        if rrule.get('bysetpos'):
            rrule['bysetpos'] = self._integer_or_default(rrule['bysetpos'])

        return rrule

    def perform_search(self, term, recur=False):
        """Parses a search term and returns a list of matching events.
        A 'term' can consist of two parts: 'search' and 'exclude'. The
        operator '%' separates the two parts. The 'exclude' part is
        optional.
        The 'search' and 'exclude' terms use the same syntax but differ
        in one noteable way:
          - 'search' is parsed as AND. All parameters must match to
        return an event record. Note that within a parameter the '+'
        operator is still an OR.
          - 'exclude' is parsed as OR. Any parameters that match will
        exclude an event record.

        Args:
            term (str):     the search term to parse.
            recur (bool):   also include all occurrences of recurring
        events in the result set.

        Returns:
            this_events (list):   the events matching the search criteria.

        """
        # helper lambda functions for parsing search and exclude strings
        def _parse_dt_range(timestr):
            """Parses a datetime range expression and returns start and
            end datetime objects.

            Args:
                timestr (str):  the datetime range string provided.

            Returns:
                begin (obj):    a valid datetime object.
                end (obj):      a valid datetime object.

            """
            now = datetime.now(tz=self.ltz)
            origin = datetime(1969, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            if timestr.startswith("~"):
                begin = origin
                end = self._datetime_or_none(
                          timestr.replace("~", ""))
            elif timestr.endswith("~"):
                begin = self._datetime_or_none(
                            timestr.replace("~", ""))
                end = now
            elif "~" in timestr:
                times = timestr.split("~")
                begin = self._datetime_or_none(
                            times[0].strip())
                end = self._datetime_or_none(
                            times[1].strip())
            else:
                begin = self._datetime_or_none(timestr)
                end = self._datetime_or_none(timestr)
            # return a valid range, regardless
            # if the input values were bad, we'll just ignore them and
            # match all timestamps 1969-01-01 to present.
            if not begin:
                begin = origin
            if not end:
                end = now
            # in the case that an end date was provided without a time,
            # set the time to the last second of the date to match any
            # time in that day.
            elif end.hour == 0 and end.minute == 0:
                end = end.replace(hour=23, minute=59, second=59)
            return begin, end

        # if the exclusion operator is in the provided search term then
        # split the term into two components: search and exclude
        # otherwise, treat it as just a search term alone.
        if "%" in term:
            term = term.split("%")
            searchterm = str(term[0]).lower()
            excludeterm = str(term[1]).lower()
        else:
            searchterm = str(term).lower()
            excludeterm = None

        valid_criteria = [
            "uid=",
            "calendar=",
            "description=",
            "location=",
            "alias=",
            "tags=",
            "start=",
            "end=",
            "notes="
        ]
        # parse the search term into a dict
        if searchterm:
            if searchterm == 'any':
                search = None
            elif not any(x in searchterm for x in valid_criteria):
                # treat this as a simple description search
                search = {}
                search['description'] = searchterm.strip()
            else:
                try:
                    search = dict((k.strip(), v.strip())
                                  for k, v in (item.split('=')
                                  for item in searchterm.split(',')))
                except ValueError:
                    msg = "invalid search expression"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
        else:
            search = None

        # parse the exclude term into a dict
        if excludeterm:
            if not any(x in excludeterm for x in valid_criteria):
                # treat this as a simple description search
                exclude = {}
                exclude['description'] = excludeterm.strip()
            else:
                try:
                    exclude = dict((k.strip(), v.strip())
                                   for k, v in (item.split('=')
                                   for item in excludeterm.split(',')))
                except ValueError:
                    msg = "invalid exclude expression"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
        else:
            exclude = None

        if recur:
            this_events = self.master_view.copy()
        else:
            this_events = []
            for uid in self.events:
                event = self.parse_event(uid)
                if event['rrule']:
                    rrule = event['rrule']
                    next_start, next_end = self.calc_next_recurrence(
                            rrule, event['start'], event['end'])
                else:
                    next_start = event['start']
                    next_end = event['end']
                data = {}
                data['uid'] = uid
                data['start'] = next_start
                data['end'] = next_end
                this_events.append(data)
            this_events = sorted(this_events, key=lambda x: x['start'])

        exclude_list = []

        if exclude:
            x_uid = exclude.get('uid')
            x_alias = exclude.get('alias')
            x_calendar = exclude.get('calendar')
            x_description = exclude.get('description')
            x_location = exclude.get('location')
            x_tags = exclude.get('tags')
            if x_tags:
                x_tags = x_tags.split('+')
            x_start = exclude.get('start')
            x_end = exclude.get('end')
            x_notes = exclude.get('notes')

            for entry in this_events:
                event = self.parse_event(entry['uid'])
                remove = False
                if x_uid:
                    if entry['uid']:
                        if x_uid == entry['uid']:
                            remove = True
                if x_alias:
                    if event['alias']:
                        if x_alias == event['alias']:
                            remove = True
                if x_calendar:
                    if event['calendar']:
                        if x_calendar in event['calendar']:
                            remove = True
                if x_description:
                    if event['description']:
                        if x_description in event['description'].lower():
                            remove = True
                if x_location:
                    if event['location']:
                        if x_location in event['location'].lower():
                            remove = True
                if x_tags:
                    if event['tags']:
                        for tag in x_tags:
                            if tag in event['tags']:
                                remove = True
                if x_start:
                    if event['start']:
                        begin, end = _parse_dt_range(x_start)
                        if recur:
                            if begin <= entry['start'] <= end:
                                remove = True
                        else:
                            if begin <= event['start'] <= end:
                                remove = True
                if x_end:
                    if event['end']:
                        begin, end = _parse_dt_range(x_end)
                        if recur:
                            if begin <= entry['end'] <= end:
                                remove = True
                        else:
                            if begin <= event['end'] <= end:
                                remove = True
                if x_notes:
                    if event['notes']:
                        if x_notes in event['notes']:
                            remove = True

                if remove:
                    exclude_list.append(entry)

        # remove excluded events
        for entry in exclude_list:
            this_events.remove(entry)

        not_match = []

        if search:
            s_uid = search.get('uid')
            s_alias = search.get('alias')
            s_calendar = search.get('calendar')
            s_description = search.get('description')
            s_location = search.get('location')
            s_tags = search.get('tags')
            if s_tags:
                s_tags = s_tags.split('+')
            s_start = search.get('start')
            s_end = search.get('end')
            s_notes = search.get('notes')
            if s_notes:
                s_notes = s_notes.lower()

            for entry in this_events:
                event = self.parse_event(entry['uid'])
                remove = False
                if s_uid:
                    if entry['uid']:
                        if not s_uid == entry['uid']:
                            remove = True
                if s_alias:
                    if event['alias']:
                        if not s_alias == event['alias']:
                            remove = True
                    else:
                        remove = True
                if s_calendar:
                    if event['calendar']:
                        if (s_calendar not in
                                event['calendar']):
                            remove = True
                    else:
                        remove = True
                if s_description:
                    if event['description']:
                        if (s_description not in
                                event['description'].lower()):
                            remove = True
                    else:
                        remove = True
                if s_location:
                    if event['location']:
                        if (s_location not in
                                event['location'].lower()):
                            remove = True
                    else:
                        remove = True
                if s_tags:
                    keep = False
                    if event['tags']:
                        # searching for tags allows use of the '+' OR
                        # operator, so if we match any tag in the list
                        # then keep the entry
                        for tag in s_tags:
                            if tag in event['tags']:
                                keep = True
                    if not keep:
                        remove = True
                if s_start:
                    if event['start']:
                        begin, end = _parse_dt_range(s_start)
                        if recur:
                            if not begin <= entry['start'] <= end:
                                remove = True
                        else:
                            if not begin <= event['start'] <= end:
                                remove = True
                    else:
                        remove = True
                if s_end:
                    if event['end']:
                        begin, end = _parse_dt_range(s_end)
                        if recur:
                            if not begin <= entry['end'] <= end:
                                remove = True
                        else:
                            if not begin <= event['end'] <= end:
                                remove = True
                    else:
                        remove = True
                if s_notes:
                    if event['notes']:
                        if s_notes not in event['notes'].lower():
                            remove = True
                    else:
                        remove = True
                if remove:
                    not_match.append(entry)

        # remove the events that didn't match search criteria
        for entry in not_match:
            this_events.remove(entry)

        return this_events

    def query(self, term, limit=None, recur=False, json_output=False):
        """Perform a search for events that match a given criteria and
        print the results in plain, tab-delimited text or JSON.

        Args:
            term (str):     the criteria for which to search.
            limit (str):    filter output to specific fields (TSV only).
            recur (bool):   whether to include recurrences of recurring
        events.
            json_output (bool): output in JSON format.

        """
        result_events = self.perform_search(term, recur)
        if limit:
            limit = limit.split(',')
        events_out = {}
        events_out['events'] = []
        text_out = ""
        if len(result_events) > 0:
            for entry in result_events:
                uid = entry['uid']
                this_event = {}
                event = self.parse_event(uid)
                calendar = event["calendar"] or ""
                description = event["description"] or ""
                location = event["location"] or ""
                alias = event["alias"] or ""
                tags = event["tags"] or []
                created = event['created']
                updated = event['updated']
                if created:
                    created = self._format_timestamp(created)
                if updated:
                    updated = self._format_timestamp(updated)
                if recur and entry['start']:
                    start = self._format_timestamp(entry['start'])
                    j_start = start
                elif event['start']:
                    start = self._format_timestamp(event['start'])
                    j_start = start
                else:
                    start = ""
                    j_start = None
                if recur and entry['end']:
                    end = self._format_timestamp(entry['end'])
                    j_end = end
                elif event['end']:
                    end = self._format_timestamp(event['end'])
                    j_end = end
                else:
                    end = ""
                    j_end = None

                if limit:
                    output = ""
                    if "uid" in limit:
                        output += f"{entry['uid']}\t"
                    if "alias" in limit:
                        output += f"{alias}\t"
                    if "calendar" in limit:
                        output += f"{calendar}\t"
                    if "start" in limit:
                        output += f"{start}\t"
                    if "end" in limit:
                        output += f"{end}\t"
                    if "description" in limit:
                        output += f"{description}\t"
                    if "location" in limit:
                        output += f"{location}\t"
                    if "tags" in limit:
                        output += f"{tags}\t"
                    if output.endswith('\t'):
                        output = output.rstrip(output[-1])
                    output = f"{output}\n"
                else:
                    output = (
                        f"{entry['uid']}\t"
                        f"{alias}\t"
                        f"{calendar}\t"
                        f"{start}\t"
                        f"{end}\t"
                        f"{description}\t"
                        f"{location}\t"
                        f"{tags}\n"
                    )
                this_event['uid'] = entry['uid']
                this_event['created'] = created
                this_event['updated'] = updated
                this_event['alias'] = event['alias']
                this_event['start'] = j_start
                this_event['end'] = j_end
                this_event['calendar'] = event['calendar']
                this_event['description'] = event['description']
                this_event['location'] = event['location']
                this_event['tags'] = event['tags']
                this_event['rrule'] = event['rrule']
                this_event['organizer'] = event['organizer']
                this_event['attendees'] = event['attendees']
                this_event['reminders'] = event['reminders']
                this_event['attachments'] = event['attachments']
                this_event['notes'] = event['notes']
                events_out['events'].append(this_event)
                text_out += f"{output}"
        if json_output:
            json_out = json.dumps(events_out, indent=4)
            print(json_out)
        else:
            if text_out != "":
                print(text_out, end="")
            else:
                print("No results.")

    def refresh(self):
        """Public method to refresh data."""
        self._parse_files()
        self._calc_master_view()

    def reminders(self, interval=None):
        """Calculates reminders for all future events and prints
        reminders for the interval period.

        Args:
            interval (str):     interval for future reminders (XdYhZm).

        """
        if interval:
            seconds = self._calc_duration(interval)
        else:
            seconds = 3600
        now = datetime.now(tz=self.ltz)
        b_span = now - timedelta(seconds=60)
        e_span = now + timedelta(seconds=seconds)
        reminders_out = {}
        reminders_out['reminders'] = []
        for entry in self.master_view:
            event = self.parse_event(entry['uid'])
            start = entry['start']
            end = entry['end']
            alias = event['alias']
            description = event['description']
            location = event['location']
            reminders = event['reminders']
            notes = event['notes']
            rrule = event['rrule']
            tags = event['tags']
            if tags:
                tags = ','.join(tags)
            if reminders:
                for reminder in reminders:
                    remind = reminder.get('remind')
                    notify = reminder.get('notify')
                    if notify:
                        if notify.lower() == "email" and self.user_email:
                            notify = "email"
                        else:
                            notify = "display"
                    else:
                        notify = "display"
                    if remind:
                        dt_reminder = self._calc_reminder(
                            remind,
                            start,
                            end)
                    if b_span <= dt_reminder <= e_span:
                        startstr = start.strftime("%H:%M")
                        if start.date() == end.date():
                            endstr = end.strftime("%H:%M")
                        else:
                            endstr = end.strftime("%Y-%m-%d %H:%M")
                        locationline = (
                            f"\n + location: {location}" if location else ""
                        )
                        rruleflag = "@" if rrule else ""
                        tagline = f"\n + tags: {tags}" if tags else ""
                        noteblock = f"\n\n{notes}\n" if notes else ""
                        if notify == "email":
                            body = (
                                f"{start.strftime('%Y-%m-%d')} "
                                f"{startstr}-{endstr}{rruleflag}\n"
                                f"({alias}) {description}"
                                f"{locationline}{tagline}"
                                f"{noteblock}\nEOF"
                            )
                        else:
                            body = (
                                f"{start.strftime('%Y-%m-%d')} "
                                f"{startstr}-{endstr}{rruleflag}\n"
                                f"({alias}) {description}"
                                f"{locationline}{tagline}"
                            )
                        this_reminder = {}
                        dtstr = dt_reminder.strftime("%Y-%m-%d %H:%M")
                        this_reminder['datetime'] = dtstr
                        this_reminder['notification'] = notify
                        if notify == "email":
                            this_reminder['address'] = self.user_email
                        this_reminder['summary'] = description
                        this_reminder['body'] = body
                        reminders_out['reminders'].append(this_reminder)
        if reminders_out['reminders']:
            json_out = json.dumps(reminders_out, indent=4)
            print(json_out)

    def search(self, term, pager=False, recur=False):
        """Perform a search for events that match a given criteria and
        print the results in formatted text.

        Args:
            term (str):     the criteria for which to search.
            pager (bool):   whether to page output.
            recur (bool):   whether to include occurences of recurring
        events.

        """
        this_events = self.perform_search(term, recur=recur)
        result_events = []
        for entry in this_events:
            event = self.parse_event(entry['uid'])
            data = {}
            if recur:
                data['start'] = entry['start']
                data['end'] = entry['end']
            else:
                data['start'] = event['start']
                data['end'] = event['end']
            data['alias'] = event['alias']
            data['calendar'] = event['calendar']
            data['description'] = event['description']
            data['location'] = event['location']
            data['tags'] = event['tags']
            data['notes'] = event['notes']
            data['rrule'] = event['rrule']
            result_events.append(data)
        self._print_event_list(
                result_events,
                'search results',
                pager=pager)

    def unset(self, alias, field):
        """Clear a specified field for a given alias.

        Args:
            alias (str):    the event alias.
            field (str):    the field to clear.

        """
        alias = alias.lower()
        field = field.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            allowed_fields = [
                'calendar',
                'location',
                'tags',
                'rrule',
                'reminders',
                'organizer',
                'attendees',
                'attachments'
            ]
            if field in allowed_fields:
                if self.events[uid][field]:
                    self.events[uid][field] = None
                    event = self.parse_event(uid)
                    filename = self.event_files.get(uid)
                    if event and filename:
                        data = {
                            "event": {
                                "uid": event['uid'],
                                "created": event['created'],
                                "updated": event['updated'],
                                "alias": event['alias'],
                                "description": event['description'],
                                "location": event['location'],
                                "tags": event['tags'],
                                "start": event['start'],
                                "end": event['end'],
                                "reminders": event['reminders'],
                                "rrule": event['rrule'],
                                "organizer": event['organizer'],
                                "attendees": event['attendees'],
                                "attachments": event['attachments'],
                                "notes": event['notes']
                            }
                        }
                        # write the updated file
                        self._write_yaml_file(data, filename)
            else:
                self._handle_error(f"cannot clear field '{field}'")


class FSHandler(FileSystemEventHandler):
    """Handler to watch for file changes and refresh data from files.

    Attributes:
        shell (obj):    the calling shell object.

    """
    def __init__(self, shell):
        """Initializes an FSHandler() object."""
        self.shell = shell

    def on_any_event(self, event):
        """Refresh data in memory on data file changes.
        Args:
            event (obj):    file system event.
        """
        if event.event_type in [
                'created', 'modified', 'deleted', 'moved']:
            self.shell.do_refresh("silent")


class EventsShell(Cmd):
    """Provides methods for interactive shell use.

    Attributes:
        events (obj):     an instance of Events().

    """
    def __init__(
            self,
            events,
            completekey='tab',
            stdin=None,
            stdout=None):
        """Initializes a EventsShell() object."""
        super().__init__()
        self.events = events

        # start watchdog for data_dir changes
        # and perform refresh() on changes
        observer = Observer()
        handler = FSHandler(self)
        observer.schedule(
                handler,
                self.events.data_dir,
                recursive=True)
        observer.start()

        # class overrides for Cmd
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey
        self.doc_header = (
            "Commands (for more info type: help):"
        )
        self.ruler = "―"

        self._set_prompt()

        self.nohelp = (
            "\nNo help for %s\n"
        )
        self.do_clear(None)

        print(
            f"{APP_NAME} {APP_VERS}\n\n"
            f"Enter command (or 'help')\n"
        )

    # class method overrides
    def default(self, args):
        """Handle command aliases and unknown commands.

        Args:
            args (str): the command arguments.

        """
        if args == "quit":
            self.do_exit("")
        elif args.startswith("lsa "):
            newargs = args.split()
            newargs[0] = "agenda"
            self.do_list(' '.join(newargs))
        elif args.startswith("lsc "):
            newargs = args.split()
            newargs[0] = "custom"
            self.do_list(' '.join(newargs))
        elif args.startswith("lstd"):
            newargs = args.split()
            newargs[0] = "today"
            self.do_list(' '.join(newargs))
        elif args.startswith("lspd"):
            newargs = args.split()
            newargs[0] = "yesterday"
            self.do_list(' '.join(newargs))
        elif args.startswith("lsnd"):
            newargs = args.split()
            newargs[0] = "tomorrow"
            self.do_list(' '.join(newargs))
        elif args.startswith("lstw"):
            newargs = args.split()
            newargs[0] = "thisweek"
            self.do_list(' '.join(newargs))
        elif args.startswith("lspw"):
            newargs = args.split()
            newargs[0] = "lastweek"
            self.do_list(' '.join(newargs))
        elif args.startswith("lsnw"):
            newargs = args.split()
            newargs[0] = "nextweek"
            self.do_list(' '.join(newargs))
        elif args.startswith("lstm"):
            newargs = args.split()
            newargs[0] = "thismonth"
            self.do_list(' '.join(newargs))
        elif args.startswith("lspm"):
            newargs = args.split()
            newargs[0] = "lastmonth"
            self.do_list(' '.join(newargs))
        elif args.startswith("lsnm"):
            newargs = args.split()
            newargs[0] = "nextmonth"
            self.do_list(' '.join(newargs))
        elif args.startswith("lsty"):
            newargs = args.split()
            newargs[0] = "thisyear"
            self.do_list(' '.join(newargs))
        elif args.startswith("lspy"):
            newargs = args.split()
            newargs[0] = "lastyear"
            self.do_list(' '.join(newargs))
        elif args.startswith("lsny"):
            newargs = args.split()
            newargs[0] = "nextyear"
            self.do_list(' '.join(newargs))
        elif args.startswith("ls"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_list(' '.join(newargs[1:]))
            else:
                self.do_list("")
        elif args.startswith("rm"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_delete(' '.join(newargs[1:]))
            else:
                self.do_delete("")
        elif args.startswith("mod"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_modify(' '.join(newargs[1:]))
            else:
                self.do_modify("")
        else:
            print("\nNo such command. See 'help'.\n")

    def emptyline(self):
        """Ignore empty line entry."""

    def _set_prompt(self):
        """Set the prompt string."""
        if self.events.color_bold:
            self.prompt = "\033[1mevents\033[0m> "
        else:
            self.prompt = "events> "

    def _uid_from_alias(self, alias):
        """Get the uid for a valid alias.

        Args:
            alias (str):    The alias of the event for which to find uid.

        Returns:
            uid (str or None): The uid that matches the submitted alias.

        """
        alias = alias.lower()
        uid = None
        for event in self.events.events:
            this_alias = self.events.events[event].get("alias")
            if this_alias:
                if this_alias == alias:
                    uid = event
        return uid

    def do_archive(self, args):
        """Archive a event.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.events.archive(str(commands[0]).lower())
        else:
            self.help_archive()

    @staticmethod
    def do_clear(args):
        """Clear the terminal.

        Args:
            args (str): the command arguments, ignored.

        """
        os.system("cls" if os.name == "nt" else "clear")

    def do_config(self, args):
        """Edit the config file and reload the configuration.

        Args:
            args (str): the command arguments, ignored.

        """
        self.events.edit_config()

    def do_delete(self, args):
        """Delete an event.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.events.delete(str(commands[0]).lower())
        else:
            self.help_delete()

    def do_edit(self, args):
        """Edit an event via $EDITOR.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.events.edit(str(commands[0]).lower())
        else:
            self.help_edit()

    def do_export(self, args):
        """Search for event(s) and export to an iCalendar file.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            if len(commands) == 2:
                term = str(commands[0]).lower()
                filename = str(commands[1])
                self.events.export(term, filename)
            else:
                self.help_export()
        else:
            self.help_export()

    @staticmethod
    def do_exit(args):
        """Exit the events shell.

        Args:
            args (str): the command arguments, ignored.

        """
        sys.exit(0)

    def do_freebusy(self, args):
        """Export free/busy info to an iCalendar file.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            if len(commands) == 2:
                interval = str(commands[0]).lower()
                filename = str(commands[1])
                self.events.freebusy(interval, filename)
            else:
                self.help_freebusy()
        else:
            self.help_freebusy()

    def do_info(self, args):
        """Output info about an event.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            alias = str(commands[0]).lower()
            page = False
            if len(commands) > 1:
                if str(commands[1]) == "|":
                    page = True
            self.events.info(alias, page)
        else:
            self.help_info()

    def do_invite(self, args):
        """Sends meeting invites for an event.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            alias = str(commands[0]).lower()
            self.events.invite(alias)
        else:
            self.help_invite()

    def do_list(self, args):
        """Output a list of events.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            args = args.strip()
            pager = False
            if args.endswith('|'):
                pager = True
                args = args[:-1].strip()
            commands = args.split()
            view = str(commands[0]).lower()
            if len(commands) > 1:
                calendar = commands[1]
            else:
                calendar = None
            if view == "custom":
                try:
                    start = input("Date/time range start: ") or None
                    end = input("Date/time range end: ") or None
                    if not start or not end:
                        print(
                            "The 'custom' view requires both a 'start' "
                            "and 'end' date."
                        )
                except KeyboardInterrupt:
                    print("\nCancelled.")
                else:
                    self.events.list(
                        view,
                        start=start,
                        end=end,
                        pager=pager,
                        cal_filter=calendar)
            else:
                self.events.list(view, pager=pager, cal_filter=calendar)
        else:
            self.help_list()

    def do_modify(self, args):
        """Modify an event.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            alias = str(commands[0]).lower()
            uid = self._uid_from_alias(alias)
            if not uid:
                print(f"Alias '{alias}' not found")
            else:
                subshell = ModShell(self.events, uid, alias)
                subshell.cmdloop()
        else:
            self.help_modify()

    def do_new(self, args):
        """Evoke the new event wizard.

        Args:
            args (str): the command arguments, ignored.

        """
        try:
            self.events.new_event_wizard()
        except KeyboardInterrupt:
            print("\nCancelled.")

    def do_notes(self, args):
        """Edit event notes via $EDITOR.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.events.notes(str(commands[0]).lower())
        else:
            self.help_notes()

    def do_refresh(self, args):
        """Refresh event information if files changed on disk.

        Args:
            args (str): the command arguments, ignored.

        """
        self.events.refresh()
        if args != 'silent':
            print("Data refreshed.")

    def do_search(self, args):
        """Search for events that meet certain criteria.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            term = str(args).strip()
            if term.endswith('|'):
                term = term[:-1].strip()
                page = True
            else:
                page = False
            self.events.search(term, page)
        else:
            self.help_search()

    def do_searchall(self, args):
        """Search for events that meet certain criteria, including
        recurrences.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            term = str(commands[0])
            page = False
            if len(commands) > 1:
                if str(commands[1]) == "|":
                    page = True
            self.events.search(term, page, True)
        else:
            self.help_search()

    def help_archive(self):
        """Output help for 'archive' command."""
        print(
            '\narchive <alias>:\n'
            f'    Archive an event file to {self.events.data_dir}/archive.\n'
        )

    @staticmethod
    def help_clear():
        """Output help for 'clear' command."""
        print(
            '\nclear:\n'
            '    Clear the terminal window.\n'
        )

    @staticmethod
    def help_config():
        """Output help for 'config' command."""
        print(
            '\nconfig:\n'
            '    Edit the config file with $EDITOR and then reload '
            'the configuration and refresh data files.\n'
        )

    @staticmethod
    def help_delete():
        """Output help for 'delete' command."""
        print(
            '\ndelete (rm) <alias>:\n'
            '    Delete an event file.\n'
        )

    @staticmethod
    def help_edit():
        """Output help for 'edit' command."""
        print(
            '\nedit <alias>:\n'
            '    Edit an event file with $EDITOR.\n'
        )

    @staticmethod
    def help_exit():
        """Output help for 'exit' command."""
        print(
            '\nexit:\n'
            '    Exit the events shell.\n'
        )

    @staticmethod
    def help_export():
        """Output help for 'export' command."""
        print(
            '\nexport <term> <file>:\n'
            '    Perform a search and export the results to a file '
            'in iCalendar format.\n'
        )

    @staticmethod
    def help_freebusy():
        """Output help for 'freebusy' command."""
        print(
            '\nfreebusy <interval> <file>:\n'
            '    Export free/busy info for <interval> to a file '
            'in iCalendar format. The interval must be in the form: '
            '[Xd][Yh][Zh].\n'
        )

    @staticmethod
    def help_info():
        """Output help for 'info' command."""
        print(
            '\ninfo <alias>:\n'
            '    Show info about an event.\n'
        )

    @staticmethod
    def help_invite():
        """Output help for 'invite' command."""
        print(
            '\ninvite <alias>:\n'
            '    Send meeting invites for an event.\n'
        )

    @staticmethod
    def help_list():
        """Output help for 'list' command."""
        print(
            '\nlist (ls) <view> [calendar] [|]:\n'
            '    List events using one of the views \'agenda\', \'today\', '
            '\'tomorrow\', \'yesterday\', \'thisweek\', \'nextweek\', '
            '\'lastweek\', \'thismonth\', \'nextmonth\', \'lastmonth\', '
            '\'thisyear\', \'nextyear\', \'lastyear\', or \'custom\'. '
            'Specify a calendar as a second argument to filter the list. '
            'Add \'|\' as an addition argument to page the output.\n\n'
            '    The following command shortcuts are available:\n\n'
            '      lsa  : list agenda\n'
            '      lstd : list today\n'
            '      lspd : list yesterday\n'
            '      lsnd : list tomorrow\n'
            '      lstw : list thisweek\n'
            '      lspw : list lastweek\n'
            '      lsnw : list nextweek\n'
            '      lstm : list thismonth\n'
            '      lspm : list lastmonth\n'
            '      lsnm : list nextmonth\n'
            '      lsty : list thisyear\n'
            '      lspy : list lastyear\n'
            '      lsny : list nextyear\n'
            '      lsc  : list custom\n'
        )

    @staticmethod
    def help_modify():
        """Output help for 'modify' command."""
        print(
            '\nmodify <alias>:\n'
            '    Modify an event file.\n'
        )

    @staticmethod
    def help_new():
        """Output help for 'new' command."""
        print(
            '\nnew:\n'
            '    Create new event interactively.\n'
        )

    @staticmethod
    def help_notes():
        """Output help for 'notes' command."""
        print(
            '\nnotes <alias>:\n'
            '    Edit the notes on an event with $EDITOR. This is safer '
            'than editing the event directly with \'edit\', as it will '
            'ensure proper indentation for multi-line notes.\n'
        )

    @staticmethod
    def help_refresh():
        """Output help for 'refresh' command."""
        print(
            '\nrefresh:\n'
            '    Refresh the event information from files on disk. '
            'This is useful if changes were made to files outside of '
            'the program shell (e.g. sync\'d from another computer).\n'
        )

    @staticmethod
    def help_search():
        """Output help for 'search' command."""
        print(
            '\nsearch <term>:\n'
            '    Search for an event or events that meet some specified '
            'criteria.\n'
        )

    @staticmethod
    def help_searchall():
        """Output help for 'searchall' command."""
        print(
            '\nsearchall <term>:\n'
            '    Search for an event or events that meet some specified '
            'criteria, including all recurrences.\n'
        )


class ModShell(Cmd):
    """Subshell for modifying an event.

    Attributes:
        events (obj):   an instance of Events().
        uid (str):      the uid of the event being modified.
        alias (str):    the alias of the event being modified.

    """
    def __init__(
            self,
            events,
            uid,
            alias,
            completekey='tab',
            stdin=None,
            stdout=None):
        """Initializes a ModShell() object."""
        super().__init__()
        self.events = events
        self.uid = uid
        self.alias = alias

        # class overrides for Cmd
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey
        self.doc_header = (
            "Commands (for more info type: help):"
        )
        self.ruler = "―"

        self._set_prompt()

        self.nohelp = (
            "\nNo help for %s\n"
        )

        self.valid_attrs = [
            'attendee',
            'attachment',
            'reminder'
        ]

    # class method overrides
    def default(self, args):
        """Handle command aliases and unknown commands.

        Args:
            args (str): the command arguments.

        """
        if args.startswith("del") or args.startswith("rm"):
            newargs = args.split()
            if len(newargs) > 1:
                newargs.pop(0)
                newargs = ' '.join(newargs)
                self.do_delete(newargs)
            else:
                self.do_delete("")
        elif args.startswith("quit") or args.startswith("exit"):
            return True
        else:
            print("\nNo such command. See 'help'.\n")

    @staticmethod
    def emptyline():
        """Ignore empty line entry."""

    def _set_prompt(self):
        """Set the prompt string."""
        if self.events.color_bold:
            self.prompt = f"\033[1mmodify ({self.alias})\033[0m> "
        else:
            self.prompt = f"modify ({self.alias})> "

    def do_add(self, args):
        """Add an attribute to an event.

        Args:
            args (str): the command arguments.

        """
        commands = args.split()
        if len(commands) < 1:
            self.help_add()
        else:
            attr = str(commands[0]).lower()
            if attr not in self.valid_attrs:
                self.help_add()
            if attr == 'reminder':
                try:
                    self.events.add_new_reminder(another=False)
                except KeyboardInterrupt:
                    print("\nCancelled.")
                self.events.modify(
                    alias=self.alias,
                    add_reminder=self.events.add_reminders)
                self.events.add_reminders = None
            elif attr == 'attendee':
                try:
                    self.events.add_new_attendee(another=False)
                except KeyboardInterrupt:
                    print("\nCancelled.")
                self.events.modify(
                    alias=self.alias,
                    add_attendee=self.events.add_attendees)
                self.events.add_attendees = None
            elif attr == 'attachment':
                try:
                    self.events.add_new_attachment(another=False)
                except KeyboardInterrupt:
                    print("\nCancelled.")
                self.events.modify(
                    alias=self.alias,
                    add_attachment=self.events.add_attachments)
                self.events.add_attachments = None

    @staticmethod
    def do_clear(args):
        """Clear the terminal.

        Args:
            args (str): the command arguments, ignored.

        """
        os.system("cls" if os.name == "nt" else "clear")

    def do_delete(self, args):
        """Delete an attribute from an event.

        Args:
            args (str): the command arguments.

        """
        commands = args.split()
        if len(commands) < 2:
            self.help_delete()
        else:
            attr = str(commands[0]).lower()
            index = commands[1]
            if attr not in self.valid_attrs:
                self.help_delete()
            reminder = [index] if attr == 'reminder' else None
            attendee = [index] if attr == 'attendee' else None
            attachment = [index] if attr == 'attachment' else None

            self.events.modify(
                alias=self.alias,
                del_attendee=attendee,
                del_attachment=attachment,
                del_reminder=reminder)

    def do_calendar(self, args):
        """Modify the calendar on an event.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            calendar = str(args)
            self.events.modify(
                alias=self.alias,
                new_calendar=calendar)
        else:
            self.help_calendar()

    def do_description(self, args):
        """Modify the description on an event.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            description = str(args)
            self.events.modify(
                alias=self.alias,
                new_description=description)
        else:
            self.help_description()

    @staticmethod
    def do_done(args):
        """Exit the modify subshell.

        Args:
            args (str): the command arguments, ignored.

        """
        return True

    def do_end(self, args):
        """Modify the 'end' date on an event.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            end = str(args)
            self.events.modify(
                alias=self.alias,
                new_end=end)
        else:
            self.help_end()

    def do_info(self, args):
        """Display full details for the selected event.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            if str(commands[0]) == "|":
                self.events.info(self.alias, True)
            else:
                self.events.info(self.alias)
        else:
            self.events.info(self.alias)

    def do_location(self, args):
        """Modify the location on an event.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            location = str(args)
            self.events.modify(
                alias=self.alias,
                new_location=location)
        else:
            self.help_location()

    def do_notes(self, args):
        """Edit event notes via $EDITOR.

        Args:
            args (str):     the command arguments.

        """
        self.events.notes(self.alias)

    def do_organizer(self, args):
        """Modify the organizer of an event.

        Args:
            args (str): the command arguments.

        """
        try:
            self.events.add_new_organizer()
        except KeyboardInterrupt:
            print("\nCancelled.")
        self.events.modify(
            alias=self.alias,
            new_organizer=self.events.add_organizer)
        self.events.add_organizer = None

    def do_rrule(self, args):
        """Modify the recurrence rule on an event.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            rrule = str(args)
            self.events.modify(
                alias=self.alias,
                new_rrule=rrule)
        else:
            self.help_rrule()

    def do_start(self, args):
        """Modify the 'start' date on an event.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            start = str(args)
            self.events.modify(
                alias=self.alias,
                new_start=start)
        else:
            self.help_start()

    def do_tags(self, args):
        """Modify the tags on an event.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            tags = str(commands[0])
            self.events.modify(
                alias=self.alias,
                new_tags=tags)
        else:
            self.help_tags()

    def do_unset(self, args):
        """Clear a field on the event.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            if len(commands) > 2:
                self.help_unset()
            else:
                field = str(commands[0]).lower()
                allowed_fields = [
                        'tags',
                        'location',
                        'rrule',
                        'reminders',
                        'attendees',
                        'organizer',
                        'attachments'
                ]
                if field in allowed_fields:
                    self.events.unset(self.alias, field)
                else:
                    self.help_unset()
        else:
            self.help_unset()

    @staticmethod
    def help_add():
        """Output help for 'add' command."""
        print(
            '\nadd <attr>:\n'
            '    Add an attribute to an event record. An attribute can '
            'be one of: reminder, attendee, or attachment. The reminder '
            'expression can either be a relative duration (e.g., '
            'start-15m or due+1h) or may be a date/time expression in '
            'the form %Y-%m-%d [%H:%M]. The notification can be either '
            '"email" (for a reminder email) or "display" for an '
            'on-screen notification.\n'
        )

    @staticmethod
    def help_clear():
        """Output help for 'clear' command."""
        print(
            '\nclear:\n'
            '    Clear the terminal window.\n'
        )

    @staticmethod
    def help_calendar():
        """Output help for 'calendar' command."""
        print(
            '\ncalendar <calendar>:\n'
            '    Modify the calendar for this event.\n'
        )

    @staticmethod
    def help_delete():
        """Output help for 'delete' command."""
        print(
            '\ndelete (del, rm) <attr> <number>:\n'
            '    Delete an attribute from an event record, identified '
            'by the index number for the attribute. An attribute can be '
            'one of: reminder, attendee, attachment.\n'
        )

    @staticmethod
    def help_description():
        """Output help for 'description' command."""
        print(
            '\ndescription <description>:\n'
            '    Modify the description of this event.\n'
        )

    @staticmethod
    def help_done():
        """Output help for 'done' command."""
        print(
            '\ndone:\n'
            '    Finish modifying the event.\n'
        )

    @staticmethod
    def help_end():
        """Output help for 'end' command."""
        print(
            '\nend <%Y-%m-%d[ %H:%M]>:\n'
            '    Modify the \'end\' date on the event.\n'
        )

    @staticmethod
    def help_info():
        """Output help for 'info' command."""
        print(
            '\ninfo [|]:\n'
            '    Display details for the event. Add "|" as an'
            'argument to page the output.\n'
        )

    @staticmethod
    def help_location():
        """Output help for 'location' command."""
        print(
            '\nlocation <location>:\n'
            '    Modify the location of this event.\n'
        )

    @staticmethod
    def help_notes():
        """Output help for 'notes' command."""
        print(
            '\nnotes:\n'
            '    Edit the notes on this event with $EDITOR.\n'
        )

    @staticmethod
    def help_organizer():
        """Output help for 'organizer' command."""
        print(
            '\norganizer <organizer>:\n'
            '    Modify the organizer of this event.\n'
        )

    @staticmethod
    def help_rrule():
        """Output help for 'rrule' command."""
        print(
            '\nrrule:\n'
            '    Modify the recurrence rule of this event. The rrule '
            'expression is a comma-delimited list of key/value pairs. '
            'The following keys are supported:\n'
            '  date=          - specific recurrence date(s), delimited '
            'by semicolon (;)\n'
            '  except=        - specific exception date(s), delimited '
            'by semicolon (;)\n'
            '  freq=          - one of minutely, hourly, daily, weekly, '
            'monthly, or yearly\n'
            '  count=         - number of recurrences\n'
            '  until=         - specific end date for recurrence\n'
            '  interval=      - integer value for recurrence interval\n'
            '  byhour=        - recur by hour (0-23)\n'
            '  byweekday=     - one of SU, MO, TU, WE, TH, FR, SA\n'
            '  bymonth=       - recur by month (1-12)\n'
            '  bymonthday=    - day of month (1-31)\n'
            '  byyearday=     - day of the year (1-366)\n'
            '  byweekno=      - week of year (1-53)\n'
            '  bysetpos=      - position of occurence set (e.g., 1 for '
            'first, -1 for last, -2 for second to last\n'
        )

    @staticmethod
    def help_start():
        """Output help for 'start' command."""
        print(
            '\nstart <%Y-%m-%d[ %H:%M]>:\n'
            '    Modify the \'start\' date on this event.\n'
        )

    @staticmethod
    def help_tags():
        """Output help for 'tags' command."""
        print(
            '\ntags <tag>[,tag]:\n'
            '    Modify the tags on this event. A comma-delimted list or '
            'you may use the + and ~ notations to add or delete a tag '
            'from the existing tags.\n'
        )

    @staticmethod
    def help_unset():
        """Output help for 'unset' command."""
        print(
            '\nunset <alias> <field>:\n'
            '    Clear a specified field of the event. The field may '
            'be one of the following: tags, location, rrule, reminders, '
            'attendees, or attachments.\n'
        )


class ICSHandler():
    """Performs ICS parsing and nrrddate add/update operations.

    Attributes:
        events (obj): an instance of Events().
        icsfile (str): the icsfile to process.

    """
    def __init__(
            self,
            events,
            icsfile):
        """Initializes an ICSHandler() object."""
        self.ical = None
        self.events = events
        self.icsfile = icsfile

        # defaults
        self.ltz = tzlocal.get_localzone()
        self.mailer_cmd = self.events.mailer_cmd
        self.default_reminder = self.events.default_reminder
        self.user_email = self.events.user_email
        self.responses = {
            1: 'ACCEPTED',
            2: 'DECLINED',
            3: 'TENTATIVE',
            4: 'NONE'
        }
        self.user_response = 4
        self.user_partstat = 'NONE'
        self.user_comment = None
        self.add_reminders = None

        # event information
        self.e_method = None
        self.e_uid = None
        self.e_attendees = None
        self.e_org_name = None
        self.e_org_email = None
        self.e_org_status = None
        self.e_description = None
        self.e_location = None
        self.e_dtstart = None
        self.e_dtend = None
        self.e_next_start = None
        self.e_next_end = None
        self.e_comments = None
        self.e_notes = None
        self.e_rrule = None
        self.e_rdates = None
        self.e_exdates = None
        self.e_user_invited = False
        self.e_user_status = None
        self.nrrddate_event = None

        self._parse_input()

    def _add_to_calendar(self):
        """Adds a received event to nrrddate."""
        add_to_calendar = input("Add to calendar [N/y]?: ").lower()
        if add_to_calendar.lower() in ['y', 'yes']:
            new_calendar = input(
                    "Calendar name [default]?: ").lower() or "default"
            add_organizer = []
            if self.e_org_name:
                add_organizer.append(self.e_org_name)
            if self.e_org_email:
                add_organizer.append(self.e_org_email)
            if not add_organizer:
                add_organizer = None
            if self.e_attendees:
                add_attendees = []
                for attendee in self.e_attendees:
                    (att_name,
                     att_email,
                     att_status) = self._attendee_info(attendee)
                    this_attendee = []
                    if att_name:
                        this_attendee.append(att_name)
                    if att_email:
                        this_attendee.append(att_email)
                        if att_email == self.user_email:
                            att_status = self.user_partstat
                    if att_status:
                        this_attendee.append(att_status)
                    if this_attendee:
                        add_attendees.append(this_attendee)
            else:
                add_attendees = None
            if self.e_rrule:
                rrulekv = []
                for key, value in self.e_rrule.items():
                    if key.lower() in ['date', 'except']:
                        pretty_dates = []
                        for item in value:
                            new_date = self._format_timestamp(
                                    item, pretty=True)
                            pretty_dates.append(new_date)
                        rrulekv.append(f"{key}={','.join(pretty_dates)}")
                    elif key.lower() == 'until':
                        value = self._format_timestamp(value, pretty=True)
                        rrulekv.append(f"{key}={value}")
                    elif value:
                        rrulekv.append(f"{key}={value}")
                add_rrule = ';'.join(rrulekv).upper()
            else:
                add_rrule = None
            add_reminders = input(
                    "Add one or more reminders to "
                    "the event? [N/y]: ").lower()
            if add_reminders in ['y', 'yes']:
                self._add_new_reminder()
            self.events.new(
                calendar=new_calendar,
                description=self.e_description,
                location=self.e_location,
                start=self.e_dtstart,
                end=self.e_dtend,
                rrule=add_rrule,
                organizer=add_organizer,
                attendees=add_attendees,
                reminders=self.add_reminders,
                notes=self.e_notes)
            # reset
            self.add_reminders = None
        else:
            self._success_exit("Not added")

    def _add_another_reminder(self):
        """Asks if the user wants to add another reminder."""
        another = input("Add another reminder? [N/y]: ").lower()
        if another in ['y', 'yes']:
            self._add_new_reminder()

    def _add_confirm_reminder(
            self,
            remind,
            notify,
            another=True):
        """Confirms the reminder expression provided.

        Args:
            remind (str):   the reminder date or expression.
            notify (int):   1 (display) or 2 (email)
            another (bool): offer to add another when complete.

        """
        if not remind:
            self._error_pass("reminder date/expression "
                             "cannot be empty")
            self._add_new_reminder(another)
        else:
            if notify == 1:
                notify = 'display'
            else:
                notify = 'email'
            print(
                "\n"
                "  New reminder:\n"
                f"    dt/expr: {remind}\n"
                f"    notify by: {notify}\n"
            )
            confirm = input("Is this correct? [N/y]: ").lower()
            if confirm in ['y', 'yes']:
                data = [remind, notify]
                if not self.add_reminders:
                    self.add_reminders = []
                self.add_reminders.append(data)
                if another:
                    self._add_another_reminder()
            else:
                self._add_new_reminder(another)

    def _add_new_reminder(self, another=True):
        """Prompts the user through adding a new event reminder.

        Args:
            another (bool): offer to add another when complete.

        """
        remind = input("Reminder date/time or expression? "
                       "[default]: ") or self.default_reminder
        notify = input("Notify by (1) display, "
                       "or (2) email [1]: ") or 1
        try:
            notify = int(notify)
        except ValueError:
            notify = 1
        if notify not in [1, 2]:
            notify = 1
        self._add_confirm_reminder(remind, notify, another)

    def _ask_response(self):
        """Asks for an attendance response and updates response."""
        print(
            "\n"
            "  1. Accept\n"
            "  2. Decline\n"
            "  3. Tentative\n"
            "  4. Do not respond\n"
            "\n"
        )
        response = input("Choose response [4]: ") or 4
        try:
            response = int(response)
        except ValueError:
            response = 4
        if response not in [1, 2, 3, 4]:
            self.user_response = 4
        else:
            self.user_response = response
        self.user_partstat = self.responses[self.user_response]

        if self.user_response != 4:
            add_comment = input("Add a comment? [N/y]: ").lower()
            if add_comment in ['y', 'yes']:
                self.user_comment = input("Comment: ") or None

    @staticmethod
    def _attendee_info(address):
        """Retrieve the email and status (if available) from an
        address.

        Args:
            address (obj): A vCalAddress object.

        Returns:
            name (str): the attendee name.
            email_addr (str): the attendee email address.
            status (str):   the attendee status.

        """
        if not address:
            name = None
            email_addr = None
            status = None
        else:
            elements = address.title().split(':')
            if len(elements) > 1:
                email_addr = elements[1].lower()
                if '@' not in email_addr:
                    email_addr = None
            if 'cn' in address.params:
                name = address.params['cn']
            if name == email_addr:
                name = None
            if 'partstat' in address.params:
                status = address.params['partstat'].upper()
                if status not in [
                        'ACCEPTED',
                        'DECLINED',
                        'TENTATIVE']:
                    status = 'NONE'
            else:
                status = 'NONE'
        return name, email_addr, status

    def _datetime_or_none(self, timestr):
        """Verify a datetime object or a datetime string in ISO format
        and return a datetime object or None.

        Args:
            timestr (str): a datetime formatted string.

        Returns:
            timeobj (datetime): a valid datetime object or None.

        """
        if isinstance(timestr, datetime):
            timeobj = timestr.astimezone(tz=self.ltz)
        else:
            try:
                timeobj = dtparser.parse(timestr).astimezone(tz=self.ltz)
            except (TypeError, ValueError, dtparser.ParserError):
                timeobj = None
        return timeobj

    def _display_event(self):
        """Outputs the event details."""
        os.system("cls" if os.name == "nt" else "clear")
        console = Console()
        title = "Calendar event"
        if self.e_method:
            self.e_method = self.e_method.upper()
            if self.e_method == "REQUEST":
                title = "Calendar invitation"
            elif self.e_method == "REPLY":
                title = "Calendar reply"
            else:
                title = "Calendar event"
        else:
            title = "Calendar event"

        event_table = Table(
            title=title,
            title_justify="left",
            title_style="bold",
            box=box.SIMPLE,
            show_header=False,
            show_lines=False,
            pad_edge=False,
            collapse_padding=False,
            padding=(0, 0, 0, 0))
        event_table.add_column("field")
        event_table.add_column("data")

        if self.e_description:
            descriptiontxt = Text(self.e_description)
            event_table.add_row("description:", descriptiontxt)
        if self.e_location:
            locationtxt = Text(self.e_location)
            event_table.add_row("location:", locationtxt)
        if self.e_next_start:
            dtstarttxt = Text(self.e_next_start.strftime('%A, %Y-%m-%d %H:%M'))
            event_table.add_row("start:", dtstarttxt)
        if self.e_next_end:
            dtendtxt = Text(self.e_next_end.strftime('%A, %Y-%m-%d %H:%M'))
            event_table.add_row("end:", dtendtxt)
        if self.e_rrule:
            rrulekv = []
            for key, value in self.e_rrule.items():
                if key.lower() in ['date', 'except']:
                    pretty_dates = []
                    for item in value:
                        new_date = self._format_timestamp(
                                item, pretty=True)
                        pretty_dates.append(new_date)
                    rrulekv.append(f"{key}={','.join(pretty_dates)}")
                elif key.lower() == 'until':
                    value = self._format_timestamp(value, pretty=True)
                    rrulekv.append(f"{key}={value}")
                elif value:
                    rrulekv.append(f"{key}={value}")
            rrulestr = ';'.join(rrulekv).upper()
            rruletxt = Text(rrulestr)
            event_table.add_row("recurs:", rruletxt)
        if self.e_uid:
            uidtxt = Text(self.e_uid)
            event_table.add_row("uid:", uidtxt)
        if self.nrrddate_event:
            if self.nrrddate_event['alias']:
                aliastxt = Text(self.nrrddate_event['alias'])
                event_table.add_row("alias:", aliastxt)
        if self.e_org_name or self.e_org_email or self.e_attendees:
            event_table.add_row(" ", " ")
        if self.e_org_name and self.e_org_email:
            organizertxt = Text(f"{self.e_org_name} <{self.e_org_email}>")
            event_table.add_row("organizer:", organizertxt)
        elif self.e_org_name or self.e_org_email:
            dis_name = self.e_org_name or ""
            dis_email = self.e_org_email or ""
            organizertxt = Text(f"{dis_name}{dis_email}")
            event_table.add_row("organizer:", organizertxt)
        if self.e_attendees:
            attendees_table = Table(
                title="Attendees",
                title_justify="left",
                title_style="bold",
                box=box.SIMPLE,
                show_header=False,
                show_lines=False,
                pad_edge=False,
                collapse_padding=False,
                padding=(0, 0, 0, 0))
            attendees_table.add_column("single")
            for attendee in self.e_attendees:
                attendeetxt = Text(
                    f" - {self._format_attendee(attendee, show_status=True)}")
                attendees_table.add_row(attendeetxt)

        if self.e_comments:
            comments_table = Table(
                title="Comments",
                title_justify="left",
                title_style="bold",
                box=box.SIMPLE,
                show_header=False,
                show_lines=False,
                pad_edge=False,
                collapse_padding=False,
                padding=(0, 0, 0, 0))
            comments_table.add_column("single")
            if not isinstance(self.e_comments, list):
                self.e_comments = [self.e_comments]
            for comment in self.e_comments:
                commenttxt = Text(comment)
                comments_table.add_row(commenttxt)

        if self.e_notes:
            notes_table = Table(
                title="Notes",
                title_justify="left",
                title_style="bold",
                box=box.SIMPLE,
                show_header=False,
                show_lines=False,
                pad_edge=False,
                collapse_padding=False,
                padding=(0, 0, 0, 0))
            notes_table.add_column("single")
            notestxt = Text(self.e_notes)
            notes_table.add_row(notestxt)

        s_start = ((self.e_next_start - timedelta(hours=2))
                   .strftime("%Y-%m-%d %H:%M"))
        s_end = ((self.e_next_end + timedelta(hours=2))
                 .strftime("%Y-%m-%d %H:%M"))
        term = f"start={s_start}~{s_end}"
        adj_events = self.events.perform_search(term=term, recur=True)
        adjacent_table = Table(
            title="Adjacent events (+/- 2 hours)",
            title_justify="left",
            title_style="bold",
            box=box.SIMPLE,
            show_header=False,
            show_lines=False,
            pad_edge=False,
            collapse_padding=False,
            min_width=30,
            padding=(0, 0, 0, 0))
        adjacent_table.add_column("single")
        if adj_events:
            valid_adj = 0
            for entry in adj_events:
                uid = entry['uid']
                event = self.events.parse_event(uid)
                this_alias = event.get('alias')
                this_start = self._datetime_or_none(entry['start'])
                this_end = self._datetime_or_none(entry['end'])
                this_description = event.get('description')
                this_location = event.get('location')
                if this_start and this_end:
                    valid_adj += 1
                    if this_start.date() == this_end.date():
                        this_datestr = (
                            f'{this_start.strftime("%Y-%m-%d %H:%M")}-'
                            f'{this_end.strftime("%H:%M")}'
                        )
                    else:
                        this_datestr = (
                            f'{this_start.strftime("%Y-%m-%d %H:%M")}-'
                            f'{this_end.strftime("%Y-%m-%d %H:%M")}'
                        )
                    event_block = (
                            f"- {this_datestr}\n"
                            f"    ({this_alias}) {this_description}"
                    )
                    if this_location:
                        event_block += f"\n    + location: {this_location}"
                    adjacent_table.add_row(Text(event_block))
            if valid_adj == 0:
                adjacent_table.add_row(Text("None"))
        else:
            adjacent_table.add_row(Text("None"))

        layout = Table.grid()
        layout.add_column("single")
        layout.add_row(event_table)
        if 'attendees_table' in locals():
            layout.add_row(attendees_table)
        if 'comments_table' in locals():
            layout.add_row(comments_table)
        if 'notes_table' in locals():
            layout.add_row(notes_table)
        layout.add_row(adjacent_table)

        console.print(layout)

    @staticmethod
    def _error_exit(errormsg):
        """Print an error message and exit with a status of 1.

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')
        sys.exit(1)

    @staticmethod
    def _error_pass(errormsg):
        """Print an error message but don't exit.

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')

    def _format_attendee(self, address, show_status=False):
        """Retrieve the email and name (if available) from an
        address.

        Args:
            address (obj): A vCalAddress object.
            show_status (bool): Whether to show the attendee's status.

        Returns:
            identifier (str): the formatted name/address.

        """
        if not address:
            identifier = ''
        name, email_addr, status = self._attendee_info(address)
        if name and email_addr:
            identifier = f"{name} <{email_addr}>"
        elif name:
            identifier = name
        elif email_addr:
            identifier = email_addr
        if show_status and status:
            identifier = f"{identifier} [{status}]"
        return identifier

    @staticmethod
    def _format_timestamp(timeobj, pretty=False):
        """Convert a datetime obj to a string.

        Args:
            timeobj (datetime): a datetime object.
            pretty (bool):      return a pretty formatted string.

        Returns:
            timestamp (str): "%Y-%m-%d %H:%M:%S" or "%Y-%m-%d[ %H:%M]".

        """
        if pretty:
            if timeobj.strftime("%H:%M") == "00:00":
                timestamp = timeobj.strftime("%Y-%m-%d")
            else:
                timestamp = timeobj.strftime("%Y-%m-%d %H:%M")
        else:
            timestamp = timeobj.strftime("%Y-%m-%d %H:%M:%S")
        return timestamp

    def _generate_reply(self):
        """Generates a response ICS file.

        Returns:
            reply (str): the formatted ICS REPLY.

        """
        def _wrap(text, length=75):
            """Wraps text that exceeds a given line length, with an
            indentation of one space on the next line.
            Args:
                text (str): the text to be wrapped.
                length (int): the maximum line length (default: 75).
            Returns:
                wrapped (str): the wrapped text.
            """
            wrapper = TextWrapper(
                width=length,
                subsequent_indent=' ',
                break_long_words=True)
            wrapped = '\r\n'.join(wrapper.wrap(text))
            return wrapped

        self.ical['method'] = 'REPLY'
        lines = []
        now = datetime.now(tz=timezone.utc)
        dtstr = now.strftime("%Y%m%dT%H%M%SZ")
        for line in self.ical.content_lines():
            if 'ATTENDEE' in line:
                if self.user_email in line:
                    if "PARTSTAT=NEEDS-ACTION" in line:
                        line = line.replace(
                                "PARTSTAT=NEEDS-ACTION",
                                f"PARTSTAT={self.user_partstat}")
                        lines.append(_wrap(line))
                    elif "PARTSTAT=ACCEPTED" in line:
                        line = line.replace(
                                "PARTSTAT=ACCEPTED",
                                f"PARTSTAT={self.user_partstat}")
                        lines.append(_wrap(line))
                    elif "PARTSTAT=DECLINED" in line:
                        line = line.replace(
                                "PARTSTAT=DECLINED",
                                f"PARTSTAT={self.user_partstat}")
                        lines.append(_wrap(line))
                    elif "PARTSTAT=TENTATIVE" in line:
                        line = line.replace(
                                "PARTSTAT=TENTATIVE",
                                f"PARTSTAT={self.user_partstat}")
                        lines.append(_wrap(line))
                    if self.user_comment:
                        line = f"COMMENT:{self.user_comment}"
                        lines.append(_wrap(line))
                else:
                    lines.append(_wrap(line))
            elif line.startswith("DTSTAMP"):
                line = f"DTSTAMP:{dtstr}"
                lines.append(_wrap(line))
            else:
                lines.append(_wrap(line))

        reply = '\r\n'.join(lines)
        return reply

    @staticmethod
    def _organizer_email(address):
        """Retrieve the organizer email (if available) from an address.

        Args:
            address (obj): A vCalAddress object.

        Returns:
            org_email (str): the organizer email address.

        """
        if not address:
            org_email = None
        else:
            elements = address.title().split(':')
            if len(elements) > 1:
                org_email = elements[1].lower()
            else:
                org_email = None
            if '@' not in org_email:
                org_email = None
        return org_email

    def _parse_input(self):
        """Reads ICS info from stdin and parses the input."""
        if os.path.isfile(self.icsfile):
            try:
                with open(self.icsfile, "r", encoding="utf-8") as ics:
                    try:
                        self.ical = icalendar.Calendar.from_ical(ics.read())
                    except ValueError:
                        self._error_exit("invalid ICS data")
            except (OSError, IOError):
                self._error_exit("failure reading ICS file")
        else:
            self._error_exit("failure reading ICS file")

    def _send_reply(
            self,
            organizer,
            subject,
            status=None,
            update=False):
        """Sends an updated invitation response.

        Args:
            organizer (str): the organizer email address.
            status (str): the current attendance status (if any).
            update (bool): whether this reply updates a previous reply.

        """
        if update and status:
            print(
                f"You have previously responded to this "
                f"invitation as: {status}"
            )
            respond = input(
                    "Do you want to update that response? [N/y]: ").lower()
        else:
            respond = input("Do you want to send a response? [N/y]: ").lower()
        if respond in ['y', 'yes']:
            self._ask_response()
            if self.user_response < 4:
                reply = self._generate_reply()
                tempdir = tempfile.gettempdir()
                ics_file = os.path.join(tempdir, 'reply.ics')
                self._write_ics(ics_file, reply)
                raw_cmd = self.mailer_cmd.split()
                # look for spaces in subject and ics_file and
                # add quotes to the text if necessary
                if " " in subject:
                    subject = f'"{subject}"'
                if " " in ics_file:
                    ics_file = f'"{ics_file}"'
                this_mailer_cmd = []
                for item in raw_cmd:
                    if item == '%s':
                        this_mailer_cmd.append(subject)
                    elif item == '%a':
                        this_mailer_cmd.append(ics_file)
                    elif item == '%r':
                        this_mailer_cmd.append(organizer)
                    else:
                        this_mailer_cmd.append(item)
                this_mailer_cmd = ' '.join(this_mailer_cmd)
                try:
                    subprocess.run(
                        this_mailer_cmd,
                        capture_output=True,
                        check=True,
                        shell=True)
                except subprocess.CalledProcessError:
                    self._error_exit(f"failure sending invite to {organizer}")
                else:
                    os.remove(ics_file)
                    if self.user_comment:
                        print(
                            f"Response {self.user_partstat} "
                            "sent with comment:\n"
                            f"\"{self.user_comment}\""
                        )
                    else:
                        print(f"Response {self.user_partstat} sent.")
                    if not update and self.user_response != 2:
                        self._add_to_calendar()
            else:
                print("Response not sent.")
                if not update:
                    self._add_to_calendar()
        else:
            print("Response not sent.")
            if not update:
                self._add_to_calendar()

    @staticmethod
    def _success_exit(successmsg):
        """Print a message, pause for two seconds, and then exit with a
        status of 0.

        Args:
            successmsg (str): the message to display.

        """
        print(f'{successmsg}')
        time.sleep(2)
        sys.exit(0)

    def _update_attendees(self):
        """Updates the event attendance status for event attendees."""
        # build a list of original attendees for the event
        orig_attendees = self.nrrddate_event['attendees']
        alias = self.nrrddate_event['alias']
        known_idents = []
        if orig_attendees:
            for oatt in orig_attendees:
                oatt_email = oatt.get('email')
                if oatt_email:
                    known_idents.append(oatt_email)
        update = input("Update status for event attendees? [N/y]: ").lower()
        if update in ['y', 'yes']:
            if self.e_attendees and self.e_uid:
                for attendee in self.e_attendees:
                    name, email_addr, status = self._attendee_info(attendee)
                    if email_addr and status:
                        if (email_addr in known_idents and
                                email_addr != self.e_org_email):
                            attend = self.events.attend(
                                    [self.e_uid, email_addr, status])
                            if attend == "SUCCESS":
                                print(f"Updated attendance for {email_addr}.")
                            elif attend == "NOMATCH":
                                print(
                                    "ERROR: Failed to find an attendee for "
                                    f"{email_addr} on event {self.e_uid}."
                                )
                            elif attend == "NOATTEND":
                                print(
                                    "ERROR: No attendees on event "
                                    f"{self.e_uid}."
                                )
                            elif attend == "NOEVENT":
                                print(
                                    "ERROR: Could not find event "
                                    f"{self.e_uid}."
                                )
                            else:
                                print(
                                    "ERROR: Unknown failure while updating "
                                    f"{email_addr} on event {self.e_uid}."
                                )
                        elif alias and email_addr != self.e_org_email:
                            status = status.upper()
                            if not name:
                                print(
                                    f"{email_addr} is not on the attendee "
                                    f"list for event {self.e_uid}.\n"
                                )
                            else:
                                print(
                                    f"{name} <{email_addr}> is not on the "
                                    "attendee list for event "
                                    f"{self.e_uid}.\n"
                                )
                            add_unknown = input(
                                    "Add the new attendee with status "
                                    f"{status}? [N/y]: ").lower()
                            if add_unknown in ['y', 'yes']:
                                if name:
                                    addlst = [[name, email_addr, status]]
                                else:
                                    addlst = [[email_addr, status]]
                                self.events.modify(
                                        alias=alias,
                                        add_attendee=addlst)
                                self.events.refresh()
                                print(f"Added attendee {email_addr}.")

                            else:
                                print("Not added.")

        else:
            self._success_exit("Attendance not updated.")

    def _write_ics(self, filename, data):
        """Writes ICS data to a file.

        Args:
            filename (str): the destination filename.
            data (str): the data to write.
        """
        try:
            with open(filename, "w", encoding="utf-8") as ics_file:
                ics_file.write(data)
        except (OSError, IOError):
            self._error_exit("unable to write ICS file")

    def handle_ics(self):
        """Processes the ICS file by adding a new event or by updating
        attendees to an event.

        """
        self.e_method = self.ical.get('method')
        events = self.ical.walk('vevent')
        if events:
            # there should really just be a single event
            event = events[0]
            # assemble event data
            self.e_uid = event.get('uid')
            if self.e_uid:
                self.e_uid = str(self.e_uid)
            self.e_attendees = event.get('attendee')
            if self.e_attendees:
                if not isinstance(self.e_attendees, list):
                    self.e_attendees = [self.e_attendees]
            self.e_org_name, self.e_org_email, self.e_org_status = (
                    self._attendee_info(event.get('organizer')))
            self.e_dtstart = event.get('dtstart').dt.astimezone(self.ltz)
            self.e_dtend = event.get('dtend').dt.astimezone(self.ltz)
            self.e_comments = event.get('comment')
            self.e_description = event.get('summary')
            if self.e_description:
                self.e_description = str(self.e_description)
            else:
                self.e_description = None
            self.e_location = event.get('location')
            if self.e_location:
                self.e_location = str(self.e_location)
            else:
                self.e_location = None
            self.e_notes = event.get('description')
            if self.e_notes:
                self.e_notes = str(self.e_notes)
            else:
                self.e_notes = None
            # iCal recurrence involves rrule, exrule, rdate, and exdate
            # we're ignoring exrule (does anyone actually use that?)
            #
            # nrrddate uses a single expression for rrules that includes
            # DATE= and EXCEPT= for rdate and exdate, respectively.
            # this next section gathers rrule, rdate, and exdate and
            # assembles them into a nrrddate-compatible rrule.
            event_rrule = event.get('rrule')
            event_rdates = event.get('rdate')
            event_exdates = event.get('exdate')
            # start with the rrule
            if event_rrule:
                rruletxt = event_rrule.to_ical().decode('utf-8')
            else:
                rruletxt = ""
            # get the rdates, check for validity, and generate a string
            # for DATE=, appended to rruletxt.
            if event_rdates:
                rdates = []
                rdatelst = event_rdates.to_ical().decode('utf-8').split(',')
                for rdate in rdatelst:
                    this_dt = self._datetime_or_none(rdate)
                    if this_dt:
                        rdates.append(this_dt.strftime("%Y-%m-%d %H:%M"))
                rdates = f"DATE={','.join(rdates)}"
            else:
                rdates = None
            if rdates:
                rruletxt = f"{rruletxt};{rdates}"
            # get the exdates, check for validity, and generate a string
            # for EXCEPT=, appended to rruletxt.
            if event_exdates:
                exdates = []
                exdatelst = event_exdates.to_ical().decode('utf-8').split(',')
                for exdate in exdatelst:
                    this_dt = self._datetime_or_none(exdate)
                    if this_dt:
                        exdates.append(this_dt.strftime("%Y-%m-%d %H:%M"))
                exdates = f"EXCEPT={','.join(exdates)}"
            else:
                exdates = None
            if exdates:
                rruletxt = f"{rruletxt};{exdates}"
            # if we have an rrule, parse it and create a dict obj in
            # self.e_rrule to use later. calculate the start and end
            # datetimes for the next recurrence.
            if rruletxt != "":
                self.e_rrule = self.events.parse_rrule(rruletxt)
                if self.e_rrule:  # not an empty dict or None
                    self.e_next_start, self.e_next_end = (
                        self.events.calc_next_recurrence(
                            self.e_rrule, self.e_dtstart, self.e_dtend))
                else:
                    self.e_next_start = self.e_dtstart
                    self.e_next_end = self.e_dtend
            # otherwise, this isn't a recurring event so use the dtstart
            # and dtend datetimes for the next start and end.
            else:
                self.e_next_start = self.e_dtstart
                self.e_next_end = self.e_dtend
                self.e_rrule = None
            # check the event attendees and look to see if the user is
            # invited, and if so, their current attendance status.
            if self.e_attendees:
                for attendee in self.e_attendees:
                    identifier = self._format_attendee(attendee)
                    if self.user_email in identifier:
                        self.e_user_invited = True
                        if 'partstat' in attendee.params:
                            self.e_user_status = attendee.params['partstat']
        else:
            self._error_exit("No events in ICS file.")

        if self.e_method:
            # process a response to an invitation sent by nrrddate
            if (self.e_method.upper() == 'REPLY' and
                    self.e_uid and self.e_attendees):
                if self.e_uid in self.events.events.keys():
                    # get the info from nrrddate about the event
                    self.nrrddate_event = (self.events.parse_event(self.e_uid))
                    self._display_event()
                    self._update_attendees()
                else:
                    self._display_event()
                    self._error_exit(
                            "this is a reply for an event that does"
                            " not exist in your calendar - exiting"
                    )
            # process an invitation sent by someone else
            elif (self.e_method.upper() == 'REQUEST' and
                  self.e_user_invited and self.e_uid and
                  self.e_org_email):
                if self.e_description:
                    subject = f"RSVP: {self.e_description}"
                else:
                    subject = "RSVP: Event invitation"
                self._display_event()
                if self.e_user_status:
                    self.e_user_status = self.e_user_status.upper()
                    if self.e_user_status in [
                            'ACCEPTED',
                            'DECLINED',
                            'TENTATIVE']:
                        self._send_reply(
                            self.e_org_email,
                            subject=subject,
                            status=self.e_user_status,
                            update=True)
                    else:
                        self._send_reply(self.e_org_email, subject)
                else:
                    self._send_reply(self.e_org_email, subject)
            # some other method was specified, the only thing to do is
            # view the invite and possibly add it to the calendar.
            else:
                self._display_event()
                self._add_to_calendar()
        # no method. again, just view it and offer to add it.
        else:
            self._display_event()
            self._add_to_calendar()


def parse_args():
    """Parse command line arguments.

    Returns:
        args (dict):    the command line arguments provided.

    """
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description='Terminal-based calendar management for nerds.')
    parser._positionals.title = 'commands'
    parser.set_defaults(command=None)
    subparsers = parser.add_subparsers(
        metavar=f'(for more help: {APP_NAME} <command> -h)')
    pager = subparsers.add_parser('pager', add_help=False)
    pager.add_argument(
        '-p',
        '--page',
        dest='page',
        action='store_true',
        help="page output")
    archive = subparsers.add_parser(
        'archive',
        help='archive an event')
    archive.add_argument(
        'alias',
        help='event alias')
    archive.add_argument(
        '-f',
        '--force',
        dest='force',
        action='store_true',
        help="archive without confirmation")
    archive.set_defaults(command='archive')
    config = subparsers.add_parser(
        'config',
        help='edit configuration file')
    config.set_defaults(command='config')
    delete = subparsers.add_parser(
        'delete',
        aliases=['rm'],
        help='delete an event file')
    delete.add_argument(
        'alias',
        help='event alias')
    delete.add_argument(
        '-f',
        '--force',
        dest='force',
        action='store_true',
        help="delete without confirmation")
    delete.set_defaults(command='delete')
    edit = subparsers.add_parser(
        'edit',
        help='edit an event file (uses $EDITOR)')
    edit.add_argument(
        'alias',
        help='event alias')
    edit.set_defaults(command='edit')
    export = subparsers.add_parser(
        'export',
        help='export events to iCalendar-formatted VEVENT output')
    export.add_argument(
        'term',
        help='search term')
    export.set_defaults(command='export')
    freebusy = subparsers.add_parser(
        'freebusy',
        help='export freebusy data to iCalendar-formatted VEVENT output')
    freebusy.add_argument(
        'interval',
        help='search term')
    freebusy.set_defaults(command='freebusy')
    ics = subparsers.add_parser(
        'ics',
        help='process a received ICS file')
    ics.add_argument(
        'ics_file',
        help='the ICS file to process')
    ics.set_defaults(command='ics')
    info = subparsers.add_parser(
        'info',
        parents=[pager],
        help='show info about an event')
    info.add_argument(
        'alias',
        help='the event to view')
    info.set_defaults(command='info')
    invite = subparsers.add_parser(
        'invite',
        help='send meeting invites for an event')
    invite.add_argument(
        'alias',
        help='the event for which to send invites')
    invite.set_defaults(command='invite')
    listcmd = subparsers.add_parser(
        'list',
        aliases=['ls'],
        parents=[pager],
        help='list events')
    listcmd.add_argument(
        'view',
        help='list view (today, yesterday, custom, etc.)')
    listcmd.add_argument(
        '--calendar',
        dest='cal_filter',
        metavar='<calendar>',
        help='show only events for a specific calendar')
    listcmd.add_argument(
        '--start',
        dest='cstart',
        metavar='<datetime>',
        help='start date/time for custom range')
    listcmd.add_argument(
        '--end',
        dest='cend',
        metavar='<datetime>',
        help='end date/time for custom range')
    listcmd.set_defaults(command='list')
    # list shortcuts
    lsa = subparsers.add_parser('lsa', parents=[pager])
    lsa.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lsa.set_defaults(command='lsa')
    lstd = subparsers.add_parser('lstd', parents=[pager])
    lstd.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lstd.set_defaults(command='lstd')
    lsnd = subparsers.add_parser('lsnd', parents=[pager])
    lsnd.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lsnd.set_defaults(command='lsnd')
    lspd = subparsers.add_parser('lspd', parents=[pager])
    lspd.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lspd.set_defaults(command='lspd')
    lstw = subparsers.add_parser('lstw', parents=[pager])
    lstw.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lstw.set_defaults(command='lstw')
    lsnw = subparsers.add_parser('lsnw', parents=[pager])
    lsnw.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lsnw.set_defaults(command='lsnw')
    lspw = subparsers.add_parser('lspw', parents=[pager])
    lspw.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lspw.set_defaults(command='lspw')
    lstm = subparsers.add_parser('lstm', parents=[pager])
    lstm.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lstm.set_defaults(command='lstm')
    lsnm = subparsers.add_parser('lsnm', parents=[pager])
    lsnm.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lsnm.set_defaults(command='lsnm')
    lspm = subparsers.add_parser('lspm', parents=[pager])
    lspm.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lspm.set_defaults(command='lspm')
    lsty = subparsers.add_parser('lsty', parents=[pager])
    lsty.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lsty.set_defaults(command='lsty')
    lsny = subparsers.add_parser('lsny', parents=[pager])
    lsny.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lsny.set_defaults(command='lsny')
    lspy = subparsers.add_parser('lspy', parents=[pager])
    lspy.add_argument(
        '--calendar',
        dest='cal_filter',
        help='show only events for a specific calendar')
    lspy.set_defaults(command='lspy')
    modify = subparsers.add_parser(
        'modify',
        aliases=['mod'],
        help='modify an event')
    modify.add_argument(
        'alias',
        help='the event to modify')
    modify.add_argument(
        '--calendar',
        metavar='<calendar>',
        help='event calendar')
    modify.add_argument(
        '--description',
        metavar='<description>',
        help='event description')
    modify.add_argument(
        '--end',
        metavar='<datetime|expression>',
        help='event end date or duration')
    modify.add_argument(
        '--location',
        metavar='<location>',
        help='event location')
    modify.add_argument(
        '--notes',
        metavar='<text>',
        help='notes about the event')
    modify.add_argument(
        '--organizer',
        metavar=('<name>', 'email address'),
        nargs='+',
        dest='organizer',
        help='organizer name and email address')
    modify.add_argument(
        '--rrule',
        metavar='<expression>',
        help='recurrence rule expression')
    modify.add_argument(
        '--start',
        metavar='<datetime>',
        help='event start date/time')
    modify.add_argument(
        '--tags',
        metavar='<tag>[,tag]',
        help='event tag(s)')
    modify.add_argument(
        '--add-attachment',
        metavar='<url>',
        dest='add_attachment',
        action='append',
        help='add event attachment')
    modify.add_argument(
        '--add-attendee',
        metavar=('<name> [email address]', 'status'),
        nargs='+',
        dest='add_attendee',
        action='append',
        help='add event attendee')
    modify.add_argument(
        '--add-reminder',
        metavar=('<datetime|expression>', 'display|email'),
        nargs='+',
        dest='add_reminder',
        action='append',
        help='add event reminder')
    modify.add_argument(
        '--del-attachment',
        metavar='<index>',
        dest='del_attachment',
        action='append',
        help='delete event attachment')
    modify.add_argument(
        '--del-attendee',
        metavar='<index>',
        dest='del_attendee',
        action='append',
        help='delete event attendee')
    modify.add_argument(
        '--del-reminder',
        metavar='<index>',
        dest='del_reminder',
        action='append',
        help='delete event reminder')
    modify.set_defaults(command='modify')
    new = subparsers.add_parser(
        'new',
        help='create a new event')
    new.add_argument(
        'description',
        help='event description')
    new.add_argument(
        '--attachment',
        metavar='<url>',
        action='append',
        dest='attachments',
        help='attachment URL')
    new.add_argument(
        '--attendee',
        metavar=('<name> [email address]', 'status'),
        nargs='+',
        action='append',
        dest='attendees',
        help='attendee name, email address, and status')
    new.add_argument(
        '--calendar',
        metavar='<calendar>',
        help='event calendar')
    new.add_argument(
        '--end',
        metavar='<datetime|expression>',
        help='event end date or duration')
    new.add_argument(
        '--location',
        metavar='<location>',
        help='event location')
    new.add_argument(
        '--notes',
        metavar='<text>',
        help='notes about the event')
    new.add_argument(
        '--organizer',
        metavar=('<name>', 'email address'),
        nargs='+',
        dest='organizer',
        help='organizer name and email address')
    new.add_argument(
        '--reminder',
        metavar=('<datetime|expression>', 'display|email'),
        nargs='+',
        action='append',
        dest='reminders',
        help='reminder date/time or relative expression')
    new.add_argument(
        '--rrule',
        metavar='<expression>',
        help='recurrence rule expression')
    new.add_argument(
        '--start',
        metavar='<datetime>',
        help='event start date/time')
    new.add_argument(
        '--tags',
        metavar='<tag>[,tag]',
        help='event tag(s)')
    new.set_defaults(command='new')
    notes = subparsers.add_parser(
        'notes',
        help='add/update notes on an event (uses $EDITOR)')
    notes.add_argument(
        'alias',
        help='event alias')
    notes.set_defaults(command='notes')
    query = subparsers.add_parser(
        'query',
        help='search events with structured text output')
    query.add_argument(
        'term',
        help='search term')
    query.add_argument(
        '-j',
        '--json',
        dest='json',
        action='store_true',
        help="output as JSON rather than TSV")
    query.add_argument(
        '-l',
        '--limit',
        dest='limit',
        help='limit output to specific field(s)')
    query.add_argument(
        '-r',
        '--recur',
        dest='recur',
        action='store_true',
        help="include recurrences")
    query.set_defaults(command='query')
    reminders = subparsers.add_parser(
        'reminders',
        aliases=['rem'],
        help='event reminders')
    reminders.add_argument(
        'interval',
        help='reminder interval ([Xd][Yh][Zd])')
    reminders.set_defaults(command='reminders')
    search = subparsers.add_parser(
        'search',
        parents=[pager],
        help='search events')
    search.add_argument(
        'term',
        help='search term')
    search.add_argument(
        '-r',
        '--recur',
        dest='recur',
        action='store_true',
        help="include recurrences")
    search.set_defaults(command='search')
    shell = subparsers.add_parser(
        'shell',
        help='interactive shell')
    shell.set_defaults(command='shell')
    unset = subparsers.add_parser(
        'unset',
        help='clear a field from a specified event')
    unset.add_argument(
        'alias',
        help='event alias')
    unset.add_argument(
        'field',
        help='field to clear')
    unset.set_defaults(command='unset')
    version = subparsers.add_parser(
        'version',
        help='show version info')
    version.set_defaults(command='version')
    parser.add_argument(
        '-c',
        '--config',
        dest='config',
        metavar='<file>',
        help='config file')
    args = parser.parse_args()
    return parser, args


def main():
    """Entry point. Parses arguments, creates Events() object, calls
    requested method and parameters.
    """
    if os.environ.get("XDG_CONFIG_HOME"):
        config_file = os.path.join(
            os.path.expandvars(os.path.expanduser(
                os.environ["XDG_CONFIG_HOME"])), APP_NAME, "config")
    else:
        config_file = os.path.expandvars(
            os.path.expanduser(DEFAULT_CONFIG_FILE))

    if os.environ.get("XDG_DATA_HOME"):
        data_dir = os.path.join(
            os.path.expandvars(os.path.expanduser(
                os.environ["XDG_DATA_HOME"])), APP_NAME)
    else:
        data_dir = os.path.expandvars(
            os.path.expanduser(DEFAULT_DATA_DIR))

    parser, args = parse_args()

    if args.config:
        config_file = os.path.expandvars(
            os.path.expanduser(args.config))

    events = Events(
        config_file,
        data_dir,
        DEFAULT_CONFIG)

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)
    elif args.command == "config":
        events.edit_config()
    elif args.command == "reminders":
        events.reminders(args.interval)
    elif args.command == "list":
        events.list(args.view,
                    start=args.cstart,
                    end=args.cend,
                    pager=args.page,
                    cal_filter=args.cal_filter)
    elif args.command == "lsa":
        events.list('agenda', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lstd":
        events.list('today', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lspd":
        events.list('yesterday', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lsnd":
        events.list('tomorrow', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lstw":
        events.list('thisweek', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lspw":
        events.list('lastweek', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lsnw":
        events.list('nextweek', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lstm":
        events.list('thismonth', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lspm":
        events.list('lastmonth', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lsnm":
        events.list('nextmonth', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lsty":
        events.list('thisyear', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lspy":
        events.list('lastyear', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lsny":
        events.list('nextyear', pager=args.page, cal_filter=args.cal_filter)
    elif args.command == "lsc":
        events.list('custom',
                    start=args.cstart,
                    end=args.cend,
                    pager=args.page,
                    cal_filter=args.cal_filter)
    elif args.command == "invite":
        events.invite(args.alias)
    elif args.command == "ics":
        icsh = ICSHandler(
            events,
            args.ics_file)
        icsh.handle_ics()
    elif args.command == "modify":
        events.modify(
            alias=args.alias,
            new_calendar=args.calendar,
            new_description=args.description,
            new_location=args.location,
            new_organizer=args.organizer,
            new_tags=args.tags,
            new_start=args.start,
            new_end=args.end,
            new_rrule=args.rrule,
            add_reminder=args.add_reminder,
            del_reminder=args.del_reminder,
            add_attendee=args.add_attendee,
            del_attendee=args.del_attendee,
            add_attachment=args.add_attachment,
            del_attachment=args.del_attachment,
            new_notes=args.notes)
    elif args.command == "new":
        events.new(
            calendar=args.calendar,
            description=args.description,
            location=args.location,
            organizer=args.organizer,
            tags=args.tags,
            start=args.start,
            end=args.end,
            reminders=args.reminders,
            rrule=args.rrule,
            attendees=args.attendees,
            attachments=args.attachments,
            notes=args.notes)
    elif args.command == "delete":
        events.delete(args.alias, args.force)
    elif args.command == "edit":
        events.edit(args.alias)
    elif args.command == "info":
        events.info(args.alias, args.page)
    elif args.command == "notes":
        events.notes(args.alias)
    elif args.command == "export":
        events.export(args.term)
    elif args.command == "freebusy":
        events.freebusy(args.interval)
    elif args.command == "archive":
        events.archive(args.alias, args.force)
    elif args.command == "search":
        events.search(args.term, args.page, recur=args.recur)
    elif args.command == "query":
        events.query(
            args.term,
            limit=args.limit,
            recur=args.recur,
            json_output=args.json)
    elif args.command == "unset":
        events.unset(args.alias, args.field)
    elif args.command == "shell":
        events.interactive = True
        shell = EventsShell(events)
        shell.cmdloop()
    elif args.command == "version":
        print(f"{APP_NAME} {APP_VERS}")
        print(APP_COPYRIGHT)
        print(APP_LICENSE)
    else:
        sys.exit(1)


# entry point
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
