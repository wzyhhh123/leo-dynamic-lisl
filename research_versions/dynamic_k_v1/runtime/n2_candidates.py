"""Independent full ADD/DROP paths; deterministic explicit-budget diagnostics."""
from .n2_actions import Hold,Add,Drop,Replace,LinkRef,implicit_releases,action_key,Setup


class CandidateSource:
    def __init__(self,validator):self.validator=validator

    def generate(self,executor,setup,*,retention_budgets=None):
        if type(setup) is not Setup or not setup.valid():raise ValueError('EXPLICIT_VALID_SETUP_REQUIRED')
        budgets=dict(retention_budgets or {})
        if any(k not in ('ADD','DROP','REPLACE') or type(v) is not int or v<0 for k,v in budgets.items()):
            raise ValueError('INVALID_EXPLICIT_RETENTION_BUDGET')
        windows=self.validator.physical.catalog.terminal_pair_candidates(executor.now,executor.satellite_ids)
        old=tuple(LinkRef.from_link(l) for _,l in sorted(executor.links.items()))
        proposed=dict(HOLD=[Hold()],ADD=[],DROP=[Drop(r) for r in old],REPLACE=[])
        for w in windows:
            a,b=w.endpoint_a,w.endpoint_b
            proposed['ADD'].append(Add(a,b,setup))
            implicit=implicit_releases(executor,a,b)
            if implicit:
                proposed['REPLACE'].append(Replace(implicit,a,b,setup,'BBM'))
            else:
                for ref in old:
                    proposed['REPLACE'].extend((Replace((ref,),a,b,setup,'BBM'),Replace((ref,),a,b,setup,'MBB')))
        retained,masks,diagnostics=[],[],{}
        for kind in ('HOLD','ADD','DROP','REPLACE'):
            legal=[]
            for action in sorted(set(proposed[kind]),key=action_key):
                verdict=self.validator.validate(executor,action)
                masks.append(dict(action=action,legal=verdict['accepted'],reason=verdict['reason']))
                if verdict['accepted']:legal.append(action)
            keep=legal[:budgets[kind]] if kind in budgets else legal
            retained.extend(keep)
            diagnostics[kind]=dict(considered=len(proposed[kind]),legal=len(legal),retained=len(keep),
                truncated=len(legal)-len(keep),budget=budgets.get(kind),
                status=('NO_LEGAL_PHYSICAL_ACTION' if not legal else
                        'LEGAL_BUT_BUDGET_TRUNCATED' if not keep else 'RETAINED'))
        return dict(candidates=retained,masks=masks,diagnostics=diagnostics,
                    time_s=executor.now,scope='ENGINEERING_ATOMIC_CANDIDATES',
                    replacement_coverage='MINIMAL_CONFLICT_SET_OR_SINGLE_OLD_WITH_FREE_ENDPOINTS')
