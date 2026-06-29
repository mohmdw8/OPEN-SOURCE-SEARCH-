#compdef opss opensourcesearch

_opss_commands() {
    local -a commands
    commands=(
        '--help:Show help message'
        '--version:Show version'
    )
    _describe 'opss' commands
}

compdef _opss_commands opss
compdef _opss_commands opensourcesearch
