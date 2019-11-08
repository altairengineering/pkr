Welcome to pkr
==============

pkr is a tool developed to help the generation of dockerfiles and docker
context and build docker images.

With pkr, you can define several `environments` for your project with
common resources, which reduces the difference between your development
workspace, the test environment and the production.

.. uml::

   @startuml
   hide empty description
   
   Environment --> Kard
   Environment : dockerfiles templates
   Environment : docker-context description
   Environment : variables (meta)
   
   driver --> Kard
   driver : docker-compose or kubernetes
   
   Kard --> [*]
   @enduml


.. toctree::
   :maxdepth: 2

   installation
   quickstart
