# /newer
This repo includes a semi-novel Open MHZ API call. By hitting the `api.openmhz.com/{system}/calls/newer?time={time}&filter-type={talkgroup|group}&filter-code={talkgroup or group id(s)}` endpoint we get the newest calls.

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

#### call object
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
Some interesting metadata could be caught from looking at srcList more. Depending on how radios are deployed, radio IDs could be staticly assigned to an officer. Evidence of such a deployment would be officers using their radio off-duty and on-duty with the same ID. If IDs are tied to officers, this could be resolved into badge/serial numbers for speakers if an additional dataset is gathered.

### direction
Always newer for calls to this endpoint. Calls are ordered from oldest to newest.

## observed weird behaviors
- sometimes calls from random times will be returned and must be filtered out
- 0 length calls will sometimes be returned
- multiple radios will "speak" without actually contributing to the audio
