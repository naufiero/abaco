from models import ExecutionsSummary, AbacoDAO

from stores import actors_store, stats_store

class UpdateCacheSummaryStats():

    # es = ExecutionsSummary(AbacoDAO)
    # why can't i reference from here


    def compute_stats_call(self, dbid):
        tot = ExecutionsSummary.compute_summary_stats(dbid)
        # returns total json object that has the summary stats


    def derived_values_call(self, name, d):
        tot = ExecutionsSummary.get_derived_value(name, d)


    def update_stats_store(self, tot):
        actor_id = tot[actor_id]
        stats_store.update(actor_id)
