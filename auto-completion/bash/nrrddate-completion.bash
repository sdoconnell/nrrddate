#/usr/bin/env bash
# bash completion for nrrddate

shopt -s progcomp
_nrrddate() {
    local cur prev firstword complete_options
    
    cur=$2
    prev=$3
	firstword=$(__get_firstword)

	GLOBAL_OPTIONS="\
        archive\
        attend\
        config\
        delete\
        edit\
        export\
        freebusy\
        info\
        invite\
        list\
        modify\
        new\
        notes\
        query\
        reminders\
        search\
        shell\
        unset\
        version\
        --config\
        --help"

    ARCHIVE_OPTIONS="--help --force"
    ATTEND_OPTIONS="--help"
    CONFIG_OPTIONS="--help"
    DELETE_OPTIONS="--help --force"
    EDIT_OPTIONS="--help"
    EXPORT_OPTIONS="--help"
    FREEBUSY_OPTIONS="--help"
    INFO_OPTIONS="--help --page"
    INVITE_OPTIONS="--help"
    LIST_OPTIONS="--help --page"
    LIST_OPTIONS_WA="--start --end --calendar"
    MODIFY_OPTIONS="--help"
    MODIFY_OPTIONS_WA="\
        --calendar\
        --description\
        --location\
        --tags\
        --start\
        --end\
        --rrule\
        --notes\
        --organizer\
        --add-reminder\
        --del-reminder\
        --add-attendee\
        --del-attendee\
        --add-attachment\
        --del-attachment"
    NEW_OPTIONS="--help"
    NEW_OPTIONS_WA="\
        --calendar\
        --location\
        --tags\
        --start\
        --end\
        --rrule\
        --notes\
        --reminder\
        --organizer\
        --attendee\
        --attachment"
    NOTES_OPTIONS="--help"
    QUERY_OPTIONS="--help --json --recur"
    QUERY_OPTIONS_WA="--limit"
    REMINDERS_OPTIONS="--help"
    SEARCH_OPTIONS="--help --page --recur"
    SHELL_OPTIONS="--help"
    UNSET_OPTIONS="--help"
    VERSION_OPTIONS="--help"

	case "${firstword}" in
	archive)
		complete_options="$ARCHIVE_OPTIONS"
		complete_options_wa=""
		;;
 	attend)
		complete_options="$ATTEND_OPTIONS"
		complete_options_wa=""
		;;
 	config)
		complete_options="$CONFIG_OPTIONS"
		complete_options_wa=""
		;;
	delete)
		complete_options="$DELETE_OPTIONS"
		complete_options_wa=""
		;;
	edit)
		complete_options="$EDIT_OPTIONS"
		complete_options_wa=""
		;;
	export)
		complete_options="$EXPORT_OPTIONS"
		complete_options_wa=""
		;;
	freebusy)
		complete_options="$FREEBUSY_OPTIONS"
		complete_options_wa=""
		;;
	info)
		complete_options="$INFO_OPTIONS"
		complete_options_wa=""
		;;
	invite)
		complete_options="$INVITE_OPTIONS"
		complete_options_wa=""
		;;
	list)
		complete_options="$LIST_OPTIONS"
		complete_options_wa="$LIST_OPTIONS_WA"
		;;
	modify)
		complete_options="$MODIFY_OPTIONS"
		complete_options_wa="$MODIFY_OPTIONS_WA"
		;;
	new)
		complete_options="$NEW_OPTIONS"
		complete_options_wa="$NEW_OPTIONS_WA"
		;;
	notes)
		complete_options="$NOTES_OPTIONS"
		complete_options_wa=""
		;;
	query)
		complete_options="$QUERY_OPTIONS"
		complete_options_wa="$QUERY_OPTIONS_WA"
		;;
	reminders)
		complete_options="$REMINDERS_OPTIONS"
		complete_options_wa=""
		;;
	search)
		complete_options="$SEARCH_OPTIONS"
		complete_options_wa=""
		;;
 	shell)
		complete_options="$SHELL_OPTIONS"
		complete_options_wa=""
		;;
	unset)
		complete_options="$UNSET_OPTIONS"
		complete_options_wa=""
		;;
	version)
		complete_options="$VERSION_OPTIONS"
		complete_options_wa=""
		;;

	*)
        complete_options="$GLOBAL_OPTIONS"
        complete_options_wa=""
		;;
	esac

    for opt in "${complete_options_wa}"; do
        [[ $opt == $prev ]] && return 1 
    done

    all_options="$complete_options $complete_options_wa"
    COMPREPLY=( $( compgen -W "$all_options" -- $cur ))
	return 0
}

__get_firstword() {
	local firstword i
 
	firstword=
	for ((i = 1; i < ${#COMP_WORDS[@]}; ++i)); do
		if [[ ${COMP_WORDS[i]} != -* ]]; then
			firstword=${COMP_WORDS[i]}
			break
		fi
	done
 
	echo $firstword
}

complete -F _nrrddate nrrddate
