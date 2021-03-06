# EncryptedBot
A bot that tweets every time calls are made on radio monitored by OpenMHZ. This bot aims to provide metadata of conversations occurring over radio channels instantly. The end goal is allowing non-automated scanners to no longer actively monitor channels that only expose meta data.

The bot includes an API endpoint for the encrypted channels of the Seattle Police Department, this can be changed for other localities or radio channels.

if i ported to node. I dont port it bc i did. no i didnt ;)

### Further Reading
- [Open MHZ API research](./API/OPENMHZ_API.md)
- [Watching SPD Analysis Bot](https://github.com/watching-spd/umbrella)

### Configuration

The following aspects of the bot can be tuned with environment variables:

 * `CALL_THRESHOLD` (integer) - minimum call duration for the bot to tweet
 * `DEBUG` ("true" or "false") - enable/disable debug logging, debug prevents tweeting
 * `REPORT_LATENCY` ("true" or "false") - enable/disable average latency reporting
 * `WINDOW_M` (integer) - number of minutes to re-use the same Twitter thread after a new message
 * `TIMEZONE` (string) - timezone for localizing message timestamps

### Docker
The docker container can be built using `docker build -t openmhz-encrypted .`.
Be sure to populate the values in the `.env` file first, then run the container with `docker run --rm -v --env-file .env openmhz-encrypted`.

If you want to tweet, you'll need to make a twitter account, apply for developer access, and then generate and save consumer keys and access tokens. Then, populate your `.env` file with these variables:
```
CONSUMER_KEY=
CONSUMER_SECRET=
ACCESS_TOKEN_KEY=
ACCESS_TOKEN_SECRET=
```

To change the configuration, add environment variables to a `.env` file and run the docker container with `docker run --rm -v --env-file .env openmhz-encrypted`.
