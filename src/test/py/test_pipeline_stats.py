from base import pipeline, clean_db
import random
import time


def test_cq_stats(pipeline, clean_db):
    """
    Verify that CQ statistics collection works
    """
    num_combiners = int(pipeline.execute('SHOW continuous_query_num_combiners').first()['continuous_query_num_combiners'])
    num_workers = int(pipeline.execute('SHOW continuous_query_num_workers').first()['continuous_query_num_workers'])

    # 10 rows
    q = 'SELECT x::integer %% 10 AS g, COUNT(*) FROM stream GROUP BY g'
    pipeline.create_cv('test_10_groups', q)

    # 1 row
    q = 'SELECT COUNT(*) FROM stream'
    pipeline.create_cv('test_1_group', q)

    values = [(random.randint(1, 1024),) for n in range(1000)]

    pipeline.insert('stream', ('x',), values)
    pipeline.insert('stream', ('x',), values)
    # Sleep a little so that the next time we insert, we force the stats collector.
    # Must be >= 1s since that's the force interval.
    time.sleep(1)
    pipeline.insert('stream', ('x',), values)
    pipeline.insert('stream', ('x',), values)

    # Sleep a little so the stats collector flushes all the stats.
    time.sleep(1)

    proc_result = list(pipeline.execute('SELECT * FROM pipeline_proc_stats'))
    cq_result = list(pipeline.execute('SELECT * FROM pipeline_query_stats'))

    proc_rows = len(proc_result)
    cq_rows = len(cq_result)

    assert proc_rows == num_combiners + num_workers
    assert cq_rows == 4

    # We get 2000 in case the first two microbatches go to the same worker
    # and the second two go to a different one. In this case, both will flush
    # the first microbatch they see, so 1000 + 1000.

    result = pipeline.execute("SELECT * FROM pipeline_query_stats WHERE name = 'test_10_groups' AND type = 'worker'").first()
    assert result['input_rows'] in [2000, 3000, 4000]

    result = pipeline.execute("SELECT * FROM pipeline_query_stats WHERE name = 'test_10_groups' AND type = 'combiner'").first()
    assert result['output_rows'] == 10

    result = pipeline.execute("SELECT * FROM pipeline_query_stats WHERE name = 'test_1_group' AND type = 'worker'").first()
    assert result['input_rows'] in [2000, 3000, 4000]

    result = pipeline.execute("SELECT * FROM pipeline_query_stats WHERE name = 'test_1_group' AND type = 'combiner'").first()
    assert result['output_rows'] == 1
