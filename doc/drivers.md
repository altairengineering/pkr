# Drivers

## base

Base driver does not implement any `container`, `image` or `deploy` based features. It is meant to template an output directory with source templates as defined in environment in the `containers` (see it as group here) dictionary.

Config (environment example):
```
default_meta:
  driver:
    name: base
containers:
  group1:
    templates:
    - template_file.template
    - template_dir
    requires: # Copied without templating
      $SRC_PATH/folder:
        dst: output
        exclude:
        - some_files_to_exclude
```

Output directory in kard folder is named `templated`

## docker

Docker driver does not implement `deploy` based features. It is meant to builds docker context and images as defined in environment in the `containers` (see it as group here) dictionary.

Config (environment example):
```
default_meta:
  driver:
    name: docker
containers:
  my_service:
    dockerfile: my_service.dockerfile.template
    requires: # Copied without templating
      $SRC_PATH/folder:
        dst: output
        exclude:
        - some_files_to_exclude
```

Output directory in kard folder is named `docker-context`

## compose

Compose driver superseed docker driver and add `deploy` features for a local deployment with `docker-compose`.

Config (environment example):
```
default_meta:
  driver:
    name: compose
    compose_file: templates/compose/docker-compose.yml.template
    compose_extension_files:
    - templates/compose/service1.yml.template
containers:
  my_service:
    dockerfile: my_service.dockerfile.template
    requires: # Copied without templating
      $SRC_PATH/folder:
        dst: output
        exclude:
        - some_files_to_exclude
```

Output file in kard folder is named `docker-compose.yml` which is builded with files from `compose` folder.
`docker-context` directory is also created (driver inheritance).

## k8s

k8s driver superseed docker driver and add `deploy` features for a deployment with `kubernetes`.

Config (environment example):
```
default_meta:
  driver:
    name: k8s
    k8s_files:
    - templates/k8s/service1.yml.template
containers:
  my_service:
    dockerfile: my_service.dockerfile.template
    requires: # Copied without templating
      $SRC_PATH/folder:
        dst: output
        exclude:
        - some_files_to_exclude
```

Output file in kard folder is named `k8s`.