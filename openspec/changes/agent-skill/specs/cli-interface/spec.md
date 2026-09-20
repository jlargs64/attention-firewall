## MODIFIED Requirements

### Requirement: Command surface
`fw` SHALL expose exactly these commands: `init`, `mission add`, `mission list`, `add`, `map`, `pull`, `override`, `done`, `drop`, `delegate`, `wait`, `resume`, `status`, `log`, `config set`, `export`, `skill show`, `skill install`, and the `--version` option. `fw --help` and `fw <command> --help` SHALL describe every option well enough that an agent reading the text alone can form a valid invocation.

#### Scenario: Help lists commands
- **WHEN** `fw --help` runs
- **THEN** every command above appears in the output and the exit code is 0

#### Scenario: Version preserved
- **WHEN** `fw --version` runs
- **THEN** the package version is printed and the exit code is 0

#### Scenario: Skill help lists subcommands
- **WHEN** `fw skill --help` runs
- **THEN** `show` and `install` appear in the output and the exit code is 0
