ZMON source code on GitHub is no longer in active development. Zalando will no longer actively review issues or merge pull-requests.

ZMON is still being used at Zalando and serves us well for many purposes. We are now deeper into our observability journey and understand better that we need other telemetry sources and tools to elevate our understanding of the systems we operate. We support the `OpenTelemetry <https://opentelemetry.io/>`_ initiative and recommended others starting their journey to begin there.

If members of the community are interested in continuing developing ZMON, consider forking it. Please review the licence before you do.

=========================
STUPS ZMON Entity Adapter
=========================

Push "global" STUPS entities such as KIO applications and teams to ZMON entity service.

.. code-block:: bash

    $ scm-source
    $ docker build -t registry.opensource.zalan.do/stups/zmon-entity-adapter:0.1 .
