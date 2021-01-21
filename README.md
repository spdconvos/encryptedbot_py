# EncryptedBot
A bot that tweets every time Seattle Police make a call over encrypted radio. This bot aims to provide metadata of conversations occurring over encrypted channels instantly. The end goal is allowing non-automated scanners to no longer actively monitor encrypted channels.

Currently the window for replies is 5 minutes, if nothing is said over encrypted in that window the bot will start a new thread. This window may be adjusted in the future as needed.

This bot might be able to be run on the same account as other automated encryption watchers, please contact me. 

if i ported to node. I dont port it bc i did. no i didnt ;)

### Further Reading
- [Open MHZ API research](./API/OPENMHZ_API.md)
- [Watching SPD bot](https://github.com/watching-spd/umbrella)

### Docker
The docker container can be built using `docker build -t openmhz-encrypted .`. Be sure to populate the values in the `secrets.json` file first, then run the container with `docker run --rm -v $(pwd)/secrets.json:/app/secrets.json openmhz-encrypted`.

If you want to tweet, you'll need to make a twitter account, apply for developer access, and then generate and save consumer keys and access tokens. Then, populate a file named `secrets.json` with these fields:
```json
{
  "consumer_key": "",
  "consumer_secret": "",
  "access_token_key": "",
  "access_token_secret": ""
}
```
