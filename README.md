# Export Module

This is a [Tyrbot](https://github.com/Budabot/Tyrbot) module to export the bot data in the [generic Anarchy Online bot export format](https://github.com/Nadybot/Nadybot/wiki/Export-Format).

## Installation

Just clone it:

```sh
cd modules/custom
git clone https://github.com/Nadybot/tyrbot-export.git export
```

## Usage

```sh
/tell Mybot !export 2021-01-05
```

It will create the export in `data/2021-01-05.json` and can be imported elsewhere.
