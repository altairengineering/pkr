# Orders of precedence

## Meta
Meta(s) are values passed to the kard during creation or update. They are available in templating context. They can come from different sources and will be merged when applicable (dictionnaries and lists).

Meta(s) follow this order of precedence (most important to lower):
 * command line `extra` (--extra)
 * command line `meta` file (--meta)
 * extensions `setup` method
 * driver `get_meta` method
 * features file
 * features `import` directive
 * environment
 * environment `import` directive

## Second level of templating

Meta(s) are computed in the Kard object from different source(s). The meta values can themselves be `Jinja` templates (See [Test files](../test/files/path1/env/dev/env.yml)).

This feature is intended to be use to limit number of top-level metas to be provided into the kard by providing another level of indirection.

Environment defines a top-level value (with a default) for the whole product (`.deployment_url` for example).

Some backend service needs this url in config, but only when deployed within this environment.

Service config file:
```
[api]
get_url = {{ .service_name.get_url }}
```

Environment file:
```
default_meta:
  deployment_url: http://dummy/
  service_name:
    get_url: '{{ deployment_url }}'
```

## Features
When creating a kard, you have several ways to provide `features`. Those will be loaded either as plugins (python code) or add-ins files from the environment.

The order of evaluation is :
 * features from `import` children
 * features from env file
 * features from meta file (passed in args)
 * features from args

# Usage

## From CLI

```
pkr <command>
```

## From API

Usage of `pkr` objects (Kard) from python code is possible but API of those objects is subject to change in future releases.

Please pin pkr version in that case.
