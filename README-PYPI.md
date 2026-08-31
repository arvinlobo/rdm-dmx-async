# rdm-dmx-async

`rdm-dmx-async` is an async-first Python library for controlling DMX512
universes and managing RDM devices. It provides packet encoding and decoding,
serial transport, RDM discovery, request/response correlation, retry policies,
device parameter APIs, and high-level network lifecycle management.

The project currently targets the ENTTEC DMX USB Pro interface. DMXKing
adapter types are present as extension points, but their framing
implementation is not yet complete.

## Install

```console
pip install rdm-dmx-async
```

## Links

- Source code and full setup/usage guide: https://github.com/arvinlobo/rdm-dmx-async
- API documentation: https://arvinlobo.github.io/rdm-dmx-async/
- Issue tracker: https://github.com/arvinlobo/rdm-dmx-async/issues
- License: MIT
