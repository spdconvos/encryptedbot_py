# /newer
This repo used to include a Open MHZ REST API call. By hitting the `api.openmhz.com/{system}/calls/newer?time={time}&filter-type={talkgroup|group}&filter-code={talkgroup or group id(s)}` endpoint you can get the newest calls.


## config/parameters {#config}
| Parameter | Description | Example(s) |
|-----------|-------------|------------|
| {system} subdomain | This is the ID for the radio system to get calls from. If you want to use this botin your locality, use the ID for your local radio system. | `kcers1b` |
| time param | The time parameter is **not** a standard UNIX timestamp!! The parameter is the whole number of seconds of the intended UNIX time with the first three decimal points tacked on at the end, so `1609533015.68102` becomes `1609533015681` or `1932012.16432` becomes `1932012164`.. | `1609533015681` |
| filter-type param | The type of filter to use. Groups are pre-rolled groups made by OpenMHZ contributors. If your system has all of the encrypted channels in its own group you can use that group. If not use talkgroup. ||
| filter-code param | The ID(s) of the group or talkgroups you want to check. If `filter-type == "group"` you can only provide one id, the API will error if you provide more than one. If you use the talkgroup filter, you can request a comma seperated list of ids. If you want to adapt this bot to your locality you can get the ID(s) from the URL of an OpenMHZ page. | `3344,3408,44912,45040` or `5ed813629818fe0025c8e245` |


## return
This API method returns a JSON object. An example of a returned object is [included here](./example.json).

### calls
This is all I care about. This is a list of call objects.

#### call model {#model}
| property name | description | type |
|---------------|-------------|------|
| \_id | OpenMHZ's ID for the call. | String |
| talkgroupNUM | The ID for the talk group that this call came from. | Integer |
| URL | The CDN URL for this call. | String |
| filename | The relative link for this call. | String |
| time | The time of the call, the format string is `%Y-%m-%dT%H:%M:%S.000%z`. Timestamp is in UTC. | String |
| srcList | A list of radio ID and time stamp objects. `\_id` is an internal OpenMHZ ID. `pos` is the start of the specific radio in the source. The end of a radio "speaking" is not recorded. `src` is the SmartNet ID for the radio. | List |
| star | The number of stars the call has at the time of the API call | Integer |
| len | The call length. | Integer |

Some interesting metadata is caught from looking at the srcList. Radios are issued to officers in a mostly static way allowing you to create a relational database between officer's personal details and the SmartNet ID of their radio.

### direction
Always newer for calls to this endpoint. Calls are ordered from oldest to newest.

## observed weird behaviors
- sometimes calls from random times will be returned and must be filtered out
- 0 length calls will sometimes be returned
- multiple radios will "speak" without actually contributing to the audio, or by adding a 0 length/overlapping sub call

# socket.io
The bot now connects to and consumes from OpenMHZ's SocketIO instance. It is located at `https://api.openmhz.com/` with the namespace `/`, using revision 4 of the Socket.IO protocol. Use the correct version of your language's Socket library.

## set up
To start getting messages from OpenMHZ:
1. Connect to the socket
2. Send a message with the name `start` containing a JSON dictionary containing the following keys:
    - `filterCode`: [described in the config section](#config)
    - `filterType`: [described in the config section](#config)
    - `filterName`: always "OpenMHZ"
    - `filterStarred`: does something, use false
    - `shortName`: the ID for your OpenMHZ system, [same as the system subdomain in the config section](#config)

## new message
The Socket will send messages with the title `new message`. The space is included in the name (it's very annoying). The contents are [the same as described in the call model section](#model). The only difference is that you only get one call at a time.

## tear down
To stop receiving messages and be nice, send the server an empty message with the name `stop` before disconnecting.
