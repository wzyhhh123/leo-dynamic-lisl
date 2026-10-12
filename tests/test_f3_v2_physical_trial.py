"""History-free physical trial must be exact or use the original path."""
from copy import deepcopy
from dataclasses import replace
import unittest
from dynamic_lisl.f3_v2.batch_executor import BatchPhysicalValidator,BatchSafetyValidator
from dynamic_lisl.f3_v2.physical_trial import physical_trial_executor
from dynamic_lisl.f3_v2.joint_action import terminal_state_hash
from dynamic_lisl.f3_v2.joint_proposer import JointSearchBudget
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog
from test_f3_v2_batch_executor import fixture,FRAME


class PhysicalTrialTests(unittest.TestCase):
    def validators(self,original):
        p=original.physical_validator
        return [BatchSafetyValidator(BatchPhysicalValidator(p.physical_layer,max_batch_replace=4,
            observation_end_s=p.observation_end_s,absolute_time_frame_id=p.absolute_time_frame_id,
            counterfactual_physical_clone=enabled),original.fixed_edges,original.policy) for enabled in (False,True)]

    def compare(self,ex,action,original):
        before=deepcopy(ex.__dict__);legacy,fast=self.validators(original)
        old=legacy.evaluate(ex,action);new=fast.evaluate(ex,action)
        self.assertEqual(old.to_dict(),new.to_dict());self.assertEqual(old.seal_sha256,new.seal_sha256)
        self.assertEqual(ex.__dict__,before)
        if old.profile and old.profile.get('executable'):
            self.assertEqual(old.profile['final_executor'].snapshot(),new.profile['final_executor'].snapshot())
        return new

    def test_bbm_mbb_mixed_complete_validation_and_history_exact(self):
        for modes in (('BBM',)*4,('MBB',)*4,('BBM','MBB','BBM','MBB')):
            with self.subTest(modes=modes):
                ex,a,v,_=fixture(modes)
                # Historical audit data must neither enter ready-time selection
                # nor be removed from the real root.
                ex.log += [{'event':'RESERVE_BOTH','details':{'predicted_ready':999},'time':0}]*50
                self.assertTrue(self.compare(ex,a,v).accepted)
                trial=physical_trial_executor(v.physical_validator.physical_layer,ex,enabled=True)
                self.assertIsNot(trial,ex);self.assertEqual(trial.log,[])
                self.assertEqual(trial.snapshot(),ex.snapshot())

    def test_nonpreemptive_tx_drain_and_absolute_time_exact(self):
        for mode in ('BBM','MBB'):
            ex,a,v,_=fixture((mode,));ex.start_tx(a.members[0].old_binding[0],4.3);ex.advance(.2)
            a=replace(a,decision_time_s=.2,decision_root_sha256=terminal_state_hash(ex))
            result=self.compare(ex,a,v);self.assertTrue(result.accepted)
            self.assertGreaterEqual(result.safety_completion_s,4.3)

    def test_zero_asymmetric_setup_and_strict_expiry_exact(self):
        for retarget,acquisition,end in ((0,0,30),(.8,.5,30),(1,1,2)):
            ex,a,v,_=fixture(('BBM',),retarget=retarget,acquisition=acquisition,ends=end)
            a=replace(a,members=(replace(a.members[0],retarget_b_s=0),))
            result=self.compare(ex,a,v)
            if end==2:self.assertEqual(result.reason,'INSUFFICIENT_LIFETIME')
        ex,a,v,_=fixture(('MBB',));catalog=v.physical_validator.physical_layer.catalog
        key=next(iter(catalog.windows));catalog.windows[key]=[replace(catalog.windows[key][0],right_censored=True)]
        self.assertTrue(self.compare(ex,a,v).accepted)

    def test_hardware_callback_reads_original_history_no_shortcut(self):
        ex,a,v,_=fixture(('MBB',))
        class HistoryHardware:
            calibration_status='ENGINEERING_HISTORY_FIXTURE'
            def check(self,state):return None if state['executor'].log else 'HISTORY_REQUIRED'
        physical=v.physical_validator.physical_layer;physical.hardware=HistoryHardware()
        self.assertIs(physical_trial_executor(physical,ex,enabled=True),ex)
        self.assertTrue(self.compare(ex,a,v).accepted)

    def test_custom_provider_catalog_and_instance_override_use_reference(self):
        ex,a,v,_=fixture(('MBB',));physical=v.physical_validator.physical_layer
        class CustomPhysical(TerminalPairPhysicalFeasibility):pass
        class CustomCatalog(TerminalPairCatalog):pass
        self.assertIs(physical_trial_executor(CustomPhysical(physical.catalog),ex,enabled=True),ex)
        windows=[w for vals in physical.catalog.windows.values() for w in vals]
        self.assertIs(physical_trial_executor(TerminalPairPhysicalFeasibility(CustomCatalog(windows,
            physical.catalog.plane_by_satellite)),ex,enabled=True),ex)
        method=physical.evaluate
        physical.evaluate=lambda *args,**kwargs:method(*args,**kwargs)
        self.assertIs(physical_trial_executor(physical,ex,enabled=True),ex)
        self.assertTrue(self.compare(ex,a,v).accepted)

    def test_explicit_legacy_path_and_clone_field_audit(self):
        ex,a,v,_=fixture(('MBB',));physical=v.physical_validator.physical_layer
        self.assertIs(physical_trial_executor(physical,ex,enabled=False),ex)
        ex.unreviewed_field=True
        with self.assertRaisesRegex(AssertionError,'CLONE_AUDIT_REQUIRED'):
            physical_trial_executor(physical,ex,enabled=True)

    def test_unauthorized_five_member_permission_is_rejected_at_configuration(self):
        ex,a,v,_=fixture(('MBB',))
        with self.assertRaisesRegex(ValueError,'MAX_BATCH_IN_1_TO_4'):
            BatchPhysicalValidator(v.physical_validator.physical_layer,max_batch_replace=5,
                observation_end_s=30,absolute_time_frame_id=FRAME)
        with self.assertRaisesRegex(ValueError,'AUTHORIZED_FOUR'):
            JointSearchBudget(16,8,4,32,5,200,200,33)


if __name__=='__main__':unittest.main(verbosity=2)
