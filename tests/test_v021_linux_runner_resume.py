"""只检验本地入口的子集与防重发边界，不连接网络或读取真实样本。"""
import unittest
from tests.qa_mineru_linux_runner import select_unreserved_rows


class RunnerResumeContract(unittest.TestCase):
    def setUp(self):
        self.plan=dict(owner='qa',batch_id='fixed',selected=[
            dict(sample_id='A',sha256='a'),dict(sample_id='B',sha256='b'),dict(sample_id='C',sha256='c')])
        self.usage=dict(owner='qa',batch_id='fixed',calls=1,files=['a'],submissions={'a:remote':True})

    def test_remaining_subset_preserves_order_and_does_not_mutate_usage(self):
        self.assertEqual([row['sample_id'] for row in select_unreserved_rows(self.plan,['B','C'],self.usage)],['B','C'])
        self.assertEqual(self.usage['calls'],1)
        self.assertTrue(self.usage['submissions']['a:remote'])

    def test_unknown_duplicate_and_empty_subset_are_rejected(self):
        for subset in (['OUTSIDE'],['B','B'],[]):
            with self.assertRaises(ValueError):
                select_unreserved_rows(self.plan,subset,self.usage)

    def test_reserved_task_and_default_replay_are_rejected(self):
        for subset in (['A'],['A','B'],None):
            with self.assertRaises(ValueError):
                select_unreserved_rows(self.plan,subset,self.usage)

    def test_other_batch_owner_and_outside_hash_are_rejected(self):
        for change in (dict(owner='other'),dict(batch_id='new'),dict(files=['unknown']),dict(calls=33)):
            with self.assertRaises(ValueError):
                select_unreserved_rows(self.plan,['B'],dict(self.usage,**change))


if __name__=='__main__':
    unittest.main()
