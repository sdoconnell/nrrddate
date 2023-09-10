---
title: NRRDDATE
section: 1
header: User Manual
footer: nrrddate 0.0.4
date: June 13, 2022
---
# NAME
nrrddate - Terminal-based calendar management for nerds.

# SYNOPSIS
**nrrddate** *command* [*OPTION*]...

# DESCRIPTION
**nrrddate** is a terminal-based calendar management program with advanced search options, formatted output, and event data stored in local text files. It can be run in either of two modes: command-line or interactive shell.

# OPTIONS
**-h**, **--help**
: Display help information.

**-c**, **--config** *file*
: Use a non-default configuration file.

# COMMANDS
**nrrddate** provides the following commands.

**archive** *alias* [*OPTION*]
: Move an event to the archive directory of your data directory (by default, $HOME/.local/share/nrrddate/archive). The user will be prompted for confirmation. Archiving an event removes it from all views, and is designed as a method to save past events while removing old events from **list** output.

    *OPTIONS*

    **-f**, **--force**
    : Force the archive operation, do not prompt for confirmation.

**config**
: Edit the **nrrddate** configuration file.

**delete (rm)** *alias* [*OPTION*]
: Delete an event and event file. The user will be prompted for confirmation.

    *OPTIONS*

    **-f**, **--force**
    : Force deletion, do not prompt for confirmation.


**edit** *alias*
: Edit an event file in the user's editor (defined by the $EDITOR environment variable). If $EDITOR is not defined, an error message will report that.

**export** *searchterm*
: Search and output results in VEVENT format, to STDOUT.

**freebusy** *interval*
: Output free/busy information in iCalendar VEVENT format for a given future interval, expressed as [Xd][Yh][Zm] (for days, hours, and minutes).

**info** *alias* [*OPTION*]
: Show the full details about an event.

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.


**invite** *alias*
: Send meeting invites for an event. The *user_name*, *user_email*, and *mailer_cmd* configuration values must be set in order to send invite emails.

**list (ls)** <*alias* | *view*> [*OPTION*]...
: List events matching a specific alias or one of the following views:

    - *agenda* (*lsa*) : Today's events that are yet to be done.
    - *today* (*lstd*) : All events for today.
    - *yesterday* (*lspd*) : All events for yesterday.
    - *tomorrow* (*lsnd*) : All events for tomorrow.
    - *thisweek* (*lstw*) : All events for this week.
    - *nextweek* (*lsnw*) : All events for next week.
    - *lastweek* (*lspw*) : All events for last week.
    - *thismonth* (*lstm*) : All events for this month.
    - *nextmonth* (*lsnm*) : All events for next month.
    - *lastmonth* (*lspm*) : All events for last month.
    - *thisyear* (*lsty*) : All events for this year.
    - *nextyear* (*lsny*) : All events for next year.
    - *lastyear* (*lspy*) : All events for last year.
    - *custom* (*lsc*) : All events in a date(time) range between **--start** and **--end**.

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.

    **--calendar** *calendar*
    : Filter listed events to only this calendar.

    **--start** *YYYY-MM-DD[ HH:MM]*
    : The start date(time) for a custom range.

    **--end** *YYYY-MM-DD[ HH:MM]*
    : The end date(time) for a custom range.

**modify (mod)** *alias* [*OPTION*]...
: Modify an event.

    *OPTIONS*

    **--calendar** *calendar*
    : The event calendar.

    **--description** *description*
    : The event description.

    **--end** <*YYYY-MM-DD[ HH:MM]* | *expression*>
    : The event end date(time). This may be either a specific date(time) or an expression of duration in the form of +[Xd][Yh][Zm] (for days, hours, and minutes). If date(time) is provided, **--end** must be later than the event *start* date.

    **--location** *location*
    : The event location.

    **--notes** *text*
    : Notes to add to the event. Be sure to properly escape the text if it includes special characters or newlines that may be interpretted by the shell. Using this option, any existing notes on the event will be replaced. This command option is included mainly for the purpose of automated note insertion (i.e., via script or command). For more reliable note editing, use the **notes** command.
   
    **--organizer** *name*
    : The organizer for an event. If an event has attendees and no *organizer* is specified, the user is assumed to be the event organizer.

    **--rrule** *rule*
    : The event's recurrence rule. See *Event Recurrence* under **NOTES**.

    **--start** *YYYY-MM-DD[ HH:MM]*
    : The event start date(time).

    **--tags** *tag[,tag]*
    : Tags assigned to the event. This can be a single tag or multiple tags in a comma-delimited list. Normally with this option, any existing tags assigned to the event will be replaced. However, this option also supports two special operators: **+** (add a tag to the existing tags) and **~** (remove a tag from the existing tags). For example, *--tags +business* will add the *business* tag to the existing tags on an event, and *--tags ~meeting,presentation* will remove both the *meeting* and *presentation* tags from an event.

    **--add-attachment** *URL*
    : Add an attachment to an event, represented by a URL.

    **--add-attendee** *name* *email address* *status*
    : Add an attendee to an event. The attendee status should be one of: ACCEPTED, DECLINED, TENTATIVE, or NONE.

    **--add-reminder** <*YYYY-MM-DD HH:MM* | *expression*> *notification*
    : Add a reminder to an event. The reminder can be defined as a specific date and time, or as a relative expression:

        - start+/-[Xd][Yh][Zm] : a reminder relative to *start*. E.g., 'start-15m' triggers a reminder 15 minutes before the *start* datetime.
        - end+/-[Xd][Yh][Zm] : a reminder relative to *end*. E.g., 'end+1h' triggers a reminder 1 hour after the *due* datetime.

        The *notification* can be one of *display* or *email*. A *display* notification will trigger a desktop notification and an *email* notification will cause a reminder email to be sent. **NOTE**: **nrrdtask** itself does not send reminders, but produces a JSON-formatted list of reminder triggers and notification types using the **reminders** command. The output of **reminders** can be parsed by an application such as **nrrdalrt** which will produce the notifications.

    **--del-attachment** *index*
    : Delete an attachment from an event. The attachment is identified by the index displayed in the output of **info**.

    **--del-attendee** *index*
    : Delete an attendee from an event. The attendee is identified by the index displayed in the output of **info**.

    **--del-reminder** *index*
    : Delete a reminder from an event. The reminder is identified by the index displayed in the output of **info**.

**new** *description* [*OPTION*]...
: Create a new event.

    *OPTIONS*

    **--attachment** *URL*
    : Add an attachment to an event, represented by a URL.

    **--attendee** *name* *email address* *status*
    : Add an attendee to an event. The attendee status should be one of: ACCEPTED, DECLINED, TENTATIVE, or NONE.

    **--calendar** *calendar*
    : The event calendar.

    **--end** <*YYYY-MM-DD[ HH:MM]* | *expression*>
    : The event end date(time). This may be either a specific date(time) or an expression of duration in the form of +[Xd][Yh][Zm] (for days, hours, and minutes). If date(time) is provided, **--end** must be later than the event *start* date.

    **--location** *location*
    : The event location.

    **--notes** *text*
    : Notes to add to the event. See **--notes** under **modify**.
   
    **--organizer** *name*
    : The organizer for an event. If an event has attendees and no *organizer* is specified, the user is assumed to be the event organizer.

    **--reminder** <*YYYY-MM-DD HH:MM* | *expression*> *notification*
    : Add a reminder to an event. See **--add-reminder** under **modify**.

    **--rrule** *rule*
    : The event's recurrence rule. See *Event Recurrence* under **NOTES**.

    **--start** *YYYY-MM-DD[ HH:MM]*
    : The event start date(time).

    **--tags** *tag[,tag]*
    : Tags assigned to the event. See **--tags** under **modify**.


**notes** *alias*
: Add or update notes on an event using the user's editor (defined by the $EDITOR environment variable). If $EDITOR is not defined, an error message will report that.

**query** *searchterm* [*OPTION*]...
: Search for one or more events and produce plain text output (by default, tab-delimited text).

    *OPTIONS*

    **-l**, **--limit**
    : Limit the output to one or more specific fields (provided as a comma-delimited list).

    **-j**, **--json**
    : Output in JSON format rather than the default tab-delimited format.


**reminders (rem)** *interval*
: Output to STDOUT event reminders in JSON format for the next interval expressed in the form [Xd][Yh][Zm] (for days, hours, and minutes).

    **Examples:**

    Both of these provide any reminders scheduled for the next hour.

        nrrddate reminders 60m
        nrrddate reminders 1h

    Show reminders scheduled for the next 2 days, 12 hours, and 45 minutes:

        nrrddate reminders 2d12h45m

**search** *searchterm* [*OPTION*]
: Search for one or more events and output a tabular list (same format as **list**).

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.


**shell**
: Launch the **nrrddate** interactive shell.

**unset** *alias* *field*
: Clear a field from a specified event.

**version**
: Show the application version information.

# NOTES

## Archiving an event
Use the **archive** subcommand to move the event file to the *archive* subdirectory in the the events data directory. Confirmation will be required for this operation unless the **--force** option is also used.

Archived events will no longer appear in lists of events. This can be useful for retaining past events without resulting in endlessly growing event lists. To review archived events, create an alterate config file with a *data_dir* pointing to the archive folder, and an alias such as:

    alias nrrddate-archive="nrrddate -c $HOME/.config/nrrddate/config.archive"

## Event recurrence
Events may have a recurrence rule (using the **--rrule** option to **new** and **modify**) to express that the event occurs more than once. The *rrule* is a semicolon-delimited list of key/value pairs.

The supported keys are:

    - date= : (str) specific recurrence date/times, delimited by comma (,).
    - except= : (str) specific date/times to be excluded, delimited by comma (,).
    - freq= : (str) one of minutely, hourly, daily, weekly, monthly, or yearly.
    - count= : (int) a specific number of recurrences.
    - until= : (str) recur until this date/time.
    - interval= : (int) the interval of recurrence.
    - byhour= : (int) recur by hour (0-23).
    - byweekday= : (str) one or more (comma-delimited) of SU, MO, TU, WE, TH, FR, or SA.
    - bymonth= : (int) recur by month (1-12).
    - bymonthday= : (int) recur by day of month (1-31).
    - byyearday= : (int) recur by day of the year (1-366).
    - byweekno= : (int) recur by week of year (1-53).
    - bysetpos= : (int) the position in an occurence set (e.g., 1 for first, -1 for last, -2 for second to last).

For example, an event that recurs on the last Monday of the month until December 31, 2021 would have the following rrule:

    freq=monthly;byweekday=MO;bysetpos=-1;until=2021-12-31

**NOTE:** ensure to properly escape or quote ';' in recurrence rules when using the --rrule option on the command line.

## Search and query
There are two command-line methods for filtering the presented list of events: **search** and **query**. These two similar-sounding functions perform very different roles.

Search results are output in the same tabular, human-readable format as that of **list**. Query results are presented in the form of tab-delimited text (by default) or JSON (if using the **-j** or **--json** option) and are primarily intended for use by other programs that are able to consume structured text output.

Search and query use the same filter syntax. The most basic form of filtering is to simply search for a keyword or string in the event description:

    nrrddate search <search_term>

**NOTE:** search terms are case-insensitive.

If the search term is present in the event description, the event will be displayed.

Optionally, a search type may be specified. The search type may be one of *uid*, *alias*, *calendar*, *description*, *tags*, *location*, *start*, *end*, or *notes*. If an invalid search type is provided, the search type will default to *description*. To specify a search type, use the format:

    nrrddate search [search_type=]<search_term>

You may combine search types in a comma-delimited structure. All search criteria must be met to return a result.

The *tags* search type may also use the optional **+** operator to search for more than one tag. Any matched tag will return a result.

The special search term *any* can be used to match all events, but is only useful in combination with an exclusion to match all records except those excluded.

## Exclusion
In addition to the search term, an exclusion term may be provided. Any match in the exclusion term will negate a match in the search term. An exclusion term is formatted in the same manner as the search term, must follow the search term, and must be denoted using the **%** operator:

    nrrddate search [search_type=]<search_term>%[exclusion_type=]<exclusion_term>

## Search examples
Search for any event description with the word "projectx":

    nrrddate search projectx

Search for any events that start on 2021-11-15:

    nrrddate search start=2021-11-15

Search for all events tagged "development" or "testing" with a start date between 2021-11-10 and 2021-11-12, except for those that have a location that contains "austin":

    nrrddate search start=2021-11-10~2021-11-12,tags=development+testing%location=austin

## Query and limit
The **query** function uses the same syntax as **search** but will output information in a form that may be read by other programs. The standard fields returned by query for tab-delimited output are:

    - uid (string)
    - alias (string)
    - calendar (string)
    - start (string)
    - end (string)
    - description (string)
    - location (string)
    - tags (list)

List fields are returned in standard Python format: ['item 1', 'item 2', ...]. Empty lists are returned as []. Empty string fields will appear as multiple tabs.

JSON output returns all fields for a record, including fields not provided in tab-delimited output.

The query function may also use the **-l** or **--limit** option. This is a comma-separated list of fields to return. The **--limit** option does not have an effect on JSON output.

## Paging
Output from **list**, **search**, and **info** can get long and run past your terminal buffer. You may use the **-p** or **--page** option in conjunction with **search**, **list**, or **info** to page output.

# FILES
**~/.config/nrrddate/config**
: Default configuration file

**~/.local/share/nrrddate**
: Default data directory

# AUTHORS
Written by Sean O'Connell <https://sdoconnell.net>.

# BUGS
Submit bug reports at: <https://github.com/sdoconnell/nrrddate/issues>

# SEE ALSO
Further documentation and sources at: <https://github.com/sdoconnell/nrrddate>
