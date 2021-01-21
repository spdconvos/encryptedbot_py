# /newer
This repo includes a semi-novel Open MHZ API call. By hitting the `/{trunk}/calls/newer?time={time}` endpoint we get the newest calls.

## {time}
The time parameter is not in UNIX time!! The parameter is the whole number of seconds of the provided UNIX time with the first three decimal points tacked on at the end.

## return
This API method returns a JSON object. An example of a returned object is [included here](./example.json).

### calls
This is all I care about. This is a list of call objects.

#### call objects
| property name | description | type |
|:-------------:|:-----------:|:----:|
| _id | OpenMHZ's ID for the call. | String |
| talkgroupNUM | The ID for the talk group that this call came from. | Integer |
| URL | The CDN URL for this call. | String |
| filename | The relative link for this call. | String |
| time | The time of the call, the format string is `%Y-%m-%dT%H:%M:%S.000%z`, time is in UTC. | String |
| srcList | An unexplored list, might be the radio IDs of the different speakers with time stamps. | List |
| star | The number of stars the call has at the time of the API call | Integer |
| len | The call length. | Integer |