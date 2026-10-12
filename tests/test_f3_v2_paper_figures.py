"""Literal temporary figure fixtures, never actual registered evidence."""
from pathlib import Path
import tempfile
import unittest
from test_f3_v2_evidence_preflight import frozen
from dynamic_lisl.f3_v2.paper_figures import opening_figure_data,render_opening_figure


def figure_fixture():
    common={'scale':160,'rho':.8,'topology_regime':'K_STAR','router':'SHORTEST_PROPAGATION_DELAY',
        'traffic':'HOTSPOT_MIGRATION','decision_cadence_s':5,'max_batch_replace':4}
    runs=[{'run_id':cid,'controller':cid+'-v2',**common} for cid in ('B0','B1','B3','B4')]
    manifest=frozen({'runs':runs,'contrasts':[],
        'registered_opening_figure_proposal':{'rho':.8,'run_ids':{c:c for c in ('B0','B1','B3','B4')},
            'phase_boundaries_s':[60,120,180,240],'no_post_result_case_replacement':True}})
    metrics={c:{'run_id':c,'outcome':'COMPLETE','J_is_complete':True,'J_bit_s':1,
        'engineering_only':False,'residual_backlog_bits':0,'delivery_ratio':1,'completion_time_s':300,
        'evaluation_end_s':300} for c in ('B0','B1','B3','B4')}
    series={c:[{'time_s':0,'queued_bits':0,'in_flight_bits':0,'arrived_bits':0,'delivered_bits':0},
        {'time_s':60,'queued_bits':2e9,'in_flight_bits':1e9,'arrived_bits':3e9,'delivered_bits':0},
        {'time_s':300,'queued_bits':0,'in_flight_bits':0,'arrived_bits':3e9,'delivered_bits':3e9}] for c in metrics}
    actions={c:[] for c in metrics};events={c:[] for c in metrics}
    actions['B4']=[{'time_s':5,'action':{'batch_id':'literal_fixture','members':[{'member_id':'a'},{'member_id':'b'}]}}]
    events['B4']=[{'time':5,'event':'LINK_DOWN','details':{'reason':'LINK_EXPIRE'}},
                  {'time':7,'event':'LINK_UP','details':{}}]
    return manifest,metrics,series,actions,events


class PaperFigureTests(unittest.TestCase):
    def test_fixed_case_raw_units_and_markers_not_sorted_by_result(self):
        args=figure_fixture();data=opening_figure_data(*args)
        self.assertEqual([c['controller'] for c in data['curves']],['B0','B1','B3','B4'])
        self.assertEqual(data['curves'][0]['points'][1]['N_bits'],3e9)
        self.assertEqual(data['curves'][3]['replace_markers'][0]['batch_size'],2)
        self.assertEqual(data['curves'][3]['physical_markers'][0]['details']['reason'],'LINK_EXPIRE')
        self.assertFalse(data['resampling']);self.assertFalse(data['curves_ranked_by_J'])

    def test_censored_status_and_raw_residual_retained(self):
        args=figure_fixture();args[1]['B4'].update(outcome='CENSORED_AT_DRAIN_LIMIT',J_is_complete=False,
            residual_backlog_bits=1e9,completion_time_s=None,evaluation_end_s=600)
        args[2]['B4'][-1].update(time_s=600,queued_bits=1e9,delivered_bits=2e9)
        data=opening_figure_data(*args)
        self.assertEqual(data['curves'][3]['outcome'],'CENSORED_AT_DRAIN_LIMIT')
        self.assertEqual(data['curves'][3]['residual_backlog_bits'],1e9)

    def test_draft_partial_or_changed_case_rejected(self):
        for fault in ('draft','partial','case','config'):
            with self.subTest(fault=fault):
                args=figure_fixture();manifest,metrics=args[:2]
                if fault=='draft':manifest['frozen']=False
                elif fault=='partial':del metrics['B1']
                else:
                    unsigned={k:v for k,v in manifest.items() if k not in ('frozen','status','canonical_sha256')}
                    if fault=='case':unsigned['registered_opening_figure_proposal']['rho']=1
                    else:unsigned['runs'][0]['max_batch_replace']=1
                    args=(frozen(unsigned),*args[1:])
                with self.assertRaises(ValueError):opening_figure_data(*args)

    def test_no_clamp_no_reorder_for_invalid_raw_timeline(self):
        for fault in ('negative','out_of_order','nan'):
            args=figure_fixture()
            if fault=='negative':args[2]['B0'][1]['queued_bits']=-1
            elif fault=='out_of_order':args[2]['B0'][1]['time_s']=301
            else:args[2]['B0'][1]['in_flight_bits']=float('nan')
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'INVALID_RAW_FIGURE_TIMELINE'):
                opening_figure_data(*args)

    def test_png_pdf_exports_and_existing_attempt_not_overwritten(self):
        data=opening_figure_data(*figure_fixture())
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp);names=render_opening_figure(data,out,engineering_fixture=True)
            self.assertEqual(names,['opening_figure.png','opening_figure.pdf'])
            self.assertTrue(all((out/name).stat().st_size>1000 for name in names))
            with self.assertRaises(FileExistsError):render_opening_figure(data,out,engineering_fixture=True)

    def test_missing_tail_cannot_be_drawn_as_complete_curve(self):
        args=figure_fixture();args[2]['B4'].pop()
        with self.assertRaisesRegex(ValueError,'INCOMPLETE_RAW_FIGURE_TIMELINE'):opening_figure_data(*args)


if __name__=='__main__':unittest.main(verbosity=2)
