# EncryptedBot
A bot that tweets every time Seattle Police make a call over encrypted radio. This bot aims to provide metadata of conversations occurring over encrypted channels instantly. The end goal is allowing non-automated scanners to no longer actively monitor encrypted channels.

Currently the window for replies is 5 minutes, if nothing is said over encrypted in that window the bot will start a new thread. This window may be adjusted in the future as needed.

This bot might be able to be run on the same account as other automated encryption watchers, please contact me. No I won't port to node ;)

### Further Reading
- [Open MHZ API research](./API/OPENMHZ_API.md)
- [Watching SPD bot](https://github.com/watching-spd/umbrella)