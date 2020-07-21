from stores import actors_store, executions_store, abaco_metrics_store

def get_actors_executions_for_report():
    """
    Collect actor and execution data about an Abaco instance for reporting purposes.
        
    :return: 
    """
    print("Starting report creation!")
    result = {'summary': {'total_actors_all': 0,
                          'total_actors_all_with_executions': 0,
                          'total_executions_all': 0,
                          'total_execution_runtime_all': 0,
                          'total_execution_cpu_all': 0,
                          'total_execution_io_all': 0,
                          'total_actors_existing': 0,
                          'total_actors_existing_with_executions': 0,
                          'total_executions_existing': 0,
                          'total_execution_runtime_existing': 0,
                          'total_execution_cpu_existing': 0,
                          'total_execution_io_existing': 0,},
              'actors': []}
    actor_info_dict = {}
    actors_with_executions = set()
    count = 0
    print("Pulling all executions now. This should take less than 60s.")
    execution_big_list = executions_store.items()
    print("Pulling all actors now.")
    actor_big_list = actors_store.items()
    print(f"Done pulling, now going through all {len(execution_big_list)} executions.")
    for execution in execution_big_list:
        actor_id = execution['actor_id']
        actor_cpu = execution['cpu']
        actor_io = execution['io']
        actor_runtime = execution['runtime']
        # add actor_id to list of actors w/ executions
        actors_with_executions.add(actor_id)
        # always add these to the totals:
        result['summary']['total_executions_all'] += 1
        result['summary']['total_execution_runtime_all'] += actor_runtime
        result['summary']['total_execution_io_all'] += actor_io
        result['summary']['total_execution_cpu_all'] += actor_cpu

        for actor in actors_store:
            # determine if actor still exists:
            if actor['db_id'] == actor_id:
                # create actor entry if not already accounted for
                if not actor_id in actor_info_dict:
                    actor_stats[actor_id] = {'actor_id': actor.get('id'),
                                             'dbid': actor_id,
                                             'owner': actor.get('owner'),
                                             'image': actor.get('image'),
                                             'total_executions': 0,
                                             'total_execution_cpu': 0,
                                             'total_execution_io': 0,
                                             'total_execution_runtime': 0}

                # write actor information if actor does exist
                actor_stats[actor_id]['total_executions'] += 1
                actor_stats[actor_id]['total_execution_runtime'] += actor_runtime
                actor_stats[actor_id]['total_execution_io'] += actor_io
                actor_stats[actor_id]['total_execution_cpu'] += actor_cpu
                # write result information if actor does exist
                result['summary']['total_executions_existing'] += 1
                result['summary']['total_execution_runtime_existing'] += actor_runtime
                result['summary']['total_execution_io_existing'] += actor_io
                result['summary']['total_execution_cpu_existing'] += actor_cpu
        count += 1
        if count % 25000 == 0:
            print(f"Current count: {count}")#, end="\r", flush=True)
    print(f"Current count: {count}")#, end="\r", flush=True)

    result['summary']['total_actors_existing_with_executions'] = len(actor_info_dict)
    result['summary']['total_actors_all_with_executions'] = len(actors_with_executions)
    result['summary']['total_actors_all'] += abaco_metrics_store['stats', 'actor_total']
    result['summary']['total_actors_existing'] += len(actors_store)

    # Return either full result or just the summary. 
    # Full result contains lots of information about existing actors.
    #return result
    return result['summary']

if __name__ == "__main__":
    print(get_actors_executions_for_report())
