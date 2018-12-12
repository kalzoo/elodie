# Elodie with Manifest

Changes from jmathai/elodie:

* Important: run Exfitool in batch mode rather than once per file, to mitigate significant fork overhead on Windows
* config file is `json` rather than `ini`, and can be read from anywhere, and is required
* target file naming convention changed
* Attribute 'origin' added
* Attributes (currently only origin) can be specified by a prefixed directory name: `origin$whatever`
* 'Db' renamed to manifest
* manifest is still written as json but each file hash has nested attributes rather than being a simple source -> destination pair. This is to (eventually) allow multiple sources and targets for each file.

The intent of many of these changes was to:

* Enable copying to multiple targets from multiple sources, including cloud targets
* Match my file naming convention to be able to filter out undated photos (ie gifs/screenshots) while