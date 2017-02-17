## Sum Reducer ##
The sum_reducer image combines dictionaries by summing the value under a given key. Thus, the values of the keys within
the dictionary must support the sum (+) operation. It can be used in conjunction with the word count actor


Register the word count actor:
```
curl -d "name=wc&image=abacosamples/wc" localhost:8000/actors
```

Register the reducer actor:
```
curl -d "name=sum&image=abacosamples/sum_reducer" localhost:8000/actors
```

Make sure to note the actor id's for the two actors and update the sample data files (e.g. small_txt.json) with the
reducer's id. Consider exporting an environment variable with the id's, e.g.
```
export wc=dfb1e8c0-f2fd-11e6-ae22-0242ac11000a-059
export sum=cb9bd990-f2fb-11e6-9983-0242ac11000a-059
```

Send a message to the word count actor to count words from the sample text:
```
curl -H "Content-type: application/json" -d "@small_txt.json" localhost:8000/actors/$wc/messages
```

This should ultimately trigger two executions, one to the word count actor and another to the sum reducer. We should
be able to check the state of the reducer after the executions are complete:
```
curl localhost:8000/actors/$sum/state
```


