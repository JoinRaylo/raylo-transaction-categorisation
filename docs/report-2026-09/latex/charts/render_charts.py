"""Rebuild vector chart PDFs from data.json; run from any directory."""
from pathlib import Path
import json, textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch
ROOT=Path(__file__).resolve().parent
for p in (ROOT.parent/'assets').glob('*.ttf'):font_manager.fontManager.addfont(str(p))
family=font_manager.FontProperties(fname=str(ROOT.parent/'assets/FKGroteskRaylo-Regular.ttf')).get_name()
plt.rcParams.update({'font.family':family,'font.size':9,'pdf.fonttype':42,'text.color':'#2D2D2D','axes.labelcolor':'#2D2D2D','xtick.color':'#6C6C6C'})
colors={'#1F5F8B':'#4252FF','#5A93BD':'#97A0FF','#C4643A':'#ED7C7C','#E0A287':'#FFD1C8','#8A939C':'#ABABAB','#2E7D5B':'#21831C'}
for id,d in json.loads((ROOT/'data.json').read_text()).items():
 n=len(d['rows']);ng=len(d['rows'][0]['groups']); legend=d.get('legend',[])
 height=n*(.39 if id in ('fig-ladder','fig-ladder-champ') else .58 if id in ('fig-gini','fig-stack') else .48 if ng==2 else .45)+.38+len(legend)*.28
 fig=plt.figure(figsize=(6.60,height));left=.395
 ax=fig.add_axes([left,(.36+len(legend)*.28)/height,.545,1-(.52+len(legend)*.28)/height])
 low=d.get('min',0);high=d['max']; span=high-low
 for i,r in enumerate(d['rows']):
  label=' '.join(r['label']) if isinstance(r['label'],list) else r['label']
  ax.text(-.70,i,textwrap.fill(label,33),transform=ax.get_yaxis_transform(),ha='left',va='center',fontsize=9,linespacing=1.22)
  for j,g in enumerate(r['groups']):
   # Give the paired bars a little more breathing room in the two taxonomy
   # ladder figures, without changing their overall row rhythm.
   pair_gap = .34 if id in ('fig-ladder','fig-ladder-champ','fig-t14','fig-stair') and ng == 2 else .29
   y=i+(j-(ng-1)/2)*pair_gap
   ax.barh(y,g['v'],height=.21 if id in ('fig-ladder','fig-ladder-champ','fig-t14','fig-stair') and ng == 2 else (.23 if ng==2 else .37),color=colors.get(g['color'],g['color']),zorder=3)
   if 'ci' in g:
    lo,hi=g['ci'];ax.errorbar(g['v'],y,xerr=[[g['v']-lo],[hi-g['v']]],fmt='none',ecolor='#2D2D2D',capsize=3,elinewidth=.8,zorder=5)
   end=g.get('ci',[0,g['v']])[1]
   ax.text(end+span*.018,y,g['text'],va='center',fontsize=8.6,fontweight='bold' if g.get('bold') else 'normal',clip_on=False)
 ax.set_ylim(n-.5,-.5);ax.set_xlim(low,high);ax.set_yticks([])
 ax.set_xticks(d['ticks'],d['tickLabels'],fontsize=8)
 ax.tick_params(axis='x',length=0,pad=7);ax.grid(axis='x',color='#E0E0E0',linewidth=.6,zorder=0)
 if low<0:ax.axvline(0,color='#6C6C6C',lw=.8)
 for sp in ax.spines.values():sp.set_visible(False)
 if legend:
  handles=[Patch(facecolor=colors.get(l['color'],l['color']),label=l['text']) for l in legend]
  fig.legend(handles=handles,loc='lower left',bbox_to_anchor=(0,0),frameon=False,ncol=1,fontsize=8.5,handlelength=1.2,labelspacing=.65,borderaxespad=0)
 fig.savefig(ROOT/(id+'.pdf'));plt.close(fig)
print('Rendered ten vector charts')
