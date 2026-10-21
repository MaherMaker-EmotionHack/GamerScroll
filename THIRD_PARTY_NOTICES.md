# Third-party software and distribution

GamerScroll's original material is GPL-3.0-only (see LICENSE and NOTICE). Dependency
code and data keep their own terms; this document does not relicense them or replace
upstream copyright notices and license texts.

## Current dependency inventory

| Component | Use | License evidence to retain |
| --- | --- | --- |
| PyQt6 | Qt Python bindings and desktop UI | GPLv3 distribution is used unless a separate commercial license is obtained. [Riverbank licensing](https://www.riverbankcomputing.com/software/pyqt/) and [FAQ](https://www.riverbankcomputing.com/commercial/license-faq). |
| Qt libraries supplied with PyQt6 wheels | Desktop runtime | Retain the actual wheel's Qt license texts and notices; Riverbank documents that GPL PyQt wheels include LGPL Qt. Check the modules and versions actually bundled. |
| pynput, pywin32 | Media Key and Windows integration | Installed distribution metadata and upstream license files. |
| requests, websockets | Local CDP HTTP/WebSocket transport | Installed distribution metadata and upstream license files. |
| loguru | Diagnostics | Installed distribution metadata and upstream license files. |
| tldextract and its bundled Public Suffix List snapshot | Site Profile domain matching | Both package and bundled-data notices; preserve attribution for the snapshot. |
| PyInstaller, Pillow | Executable packaging and original-icon generation | Tool license/exception terms and any material actually included in the output. |
| Python and transitive dependencies | Bundled interpreter and supporting libraries | Exact build-environment inventory and license files for redistributed components. |

The requirements currently allow version ranges, so this is a component inventory,
not an assertion that every future resolved dependency has been audited.

## Before distributing an executable

1. Record the source revision, Python version, and exact installed distributions
   (for example `python -m pip freeze`). Review the actual bundled components.
2. Ship LICENSE, NOTICE, this inventory, and the full applicable third-party notices
   and license texts alongside the executable. Preserve any embedded notices.
3. Provide corresponding source for the distributed GPL-covered work, including
   modifications and build instructions. Retain access to the exact third-party
   source required by the applicable licenses; a GamerScroll-only source archive
   is not a replacement for those obligations.
4. Fulfill the applicable Qt/LGPL requirements for the actual packaging method,
   including replacement/relinking and source availability where required.
5. Verify new copied source/assets have documented redistribution permission and
   attribution. AmpUp reuse is pending that evidence in this repository.

Release automation creates **draft releases** for this review. Publishing a draft
requires completing the component-specific checks above; automated builds do not
certify license compliance. No new executable release is published by this setup.
