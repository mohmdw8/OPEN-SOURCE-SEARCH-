_opss_completions() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    local opts="--help --version"

    case "${prev}" in
        opss|opensourcesearch)
            COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
            return 0
            ;;
    esac

    COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
}

complete -F _opss_completions opss
complete -F _opss_completions opensourcesearch
