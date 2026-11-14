"""Read saved results and export presentation explainers; never fit project models.

Run from the project environment: python src/13_presentation_explainers.py
Only this task's PNG/SVG figures and visual_guide.md are written.
"""
from pathlib import Path
import hashlib
import json
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import polars as pl
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/figures/presentation_explainers'
PRIVATE = ROOT / 'data/processed/stage12_modelling'
SOURCE = ROOT / 'data/processed/billboard_lyrics_corrected_2000_2022.parquet'
NAVY, BLUE, TEAL, GRAY = '#142D4E', '#2563B5', '#087F80', '#63758A'
LIGHT, EDGE = '#EEF3F7', '#CCD7E1'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 18,
    'text.color': NAVY, 'axes.labelcolor': NAVY, 'xtick.color': NAVY,
    'ytick.color': NAVY, 'axes.edgecolor': EDGE, 'figure.facecolor': 'white',
    'axes.facecolor': 'white', 'svg.fonttype': 'none'})
GUIDE = []


def base(title, subtitle):
    fig = plt.figure(figsize=(16, 9), dpi=120)
    fig.text(.045, .935, title, fontsize=29, weight='bold')
    fig.text(.045, .885, subtitle, fontsize=17, color=GRAY)
    return fig


def note(fig, text):
    fig.text(.045, .055, text, fontsize=15, va='bottom', linespacing=1.5)


def canvas(fig):
    ax = fig.add_axes([.04, .17, .92, .65])
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis('off')
    return ax


def box(ax, x, y, w, h, text, fill=LIGHT, size=20):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fill, edgecolor=EDGE, lw=1.4))
    ax.text(x+w/2, y+h/2, text, ha='center', va='center', fontsize=size, linespacing=1.5)


def arrow(ax, start, end):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle='-|>', mutation_scale=20,
                                lw=2, color=GRAY))


def save(fig, name):
    # Keep the exact 16:9 canvas; tight bounding boxes would alter the export size.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for txt in fig.findobj(matplotlib.text.Text):
        if txt.get_visible() and txt.get_text():
            b = txt.get_window_extent(renderer)
            assert b.x0 >= -1 and b.y0 >= -1 and b.x1 <= 1921 and b.y1 <= 1081, (name, txt.get_text())
    for ext in ('png', 'svg'):
        fig.savefig(OUT / f'{name}.{ext}', dpi=120, facecolor='white')
    plt.close(fig)


def guide(name, kind, question, reading, explanation, speech, limitation, sources):
    GUIDE.append(f'## {name}\n\n**{kind}.** {question}\n\n'
        f'**Read it:** {reading}\n\n**For a beginner:** {explanation}\n\n'
        f'**Say:** {speech}\n\n**Limitation:** {limitation}\n\n'
        f'**Sources:** {sources}\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = [SOURCE, PRIVATE/'out_of_fold_predictions.csv', PRIVATE/'descriptive_topics.csv',
              PRIVATE/'run_manifest.json', ROOT/'reports/lyric_preprocessing_presentation_evidence.csv',
              ROOT/'reports/topics_and_top10_prediction.md']
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    manifest = json.loads(inputs[3].read_text(encoding='utf-8'))
    report = inputs[5].read_text(encoding='utf-8')
    oof = pl.read_csv(inputs[1])
    topics = pl.read_csv(inputs[2])
    evidence = pl.read_csv(inputs[4])
    src = pl.read_parquet(SOURCE, columns=['billboard_source_row','Song','Artist','top10','peak_rank',
        'lyric_language','lyric_language_mixed_candidate','lyrics','lyrics_clean','lyrics_deduplicated'])
    eligible = src.filter(pl.col('lyric_language') == 'en')
    counts = [src.height, src.height-eligible.height, eligible.height,
              eligible['top10'].sum(), eligible.height-eligible['top10'].sum()]
    assert counts == [6546, 161, 6385, 984, 5401]
    assert counts == [manifest[k] for k in ['source_records','excluded_language','eligible','positive','negative']]
    assert oof.height == oof['billboard_source_row'].n_unique() == eligible.height
    assert oof.select('billboard_source_row','top10').sort('billboard_source_row').equals(
        eligible.select('billboard_source_row','top10').sort('billboard_source_row'))
    assert eligible.select((pl.col('top10') == (pl.col('peak_rank') <= 10)).all()).item()
    assert oof.group_by('evaluation_group').agg(pl.col('validation_fold').n_unique())['validation_fold'].max() == 1

    fig = base('Which songs entered the analysis?', 'ACTUAL SAMPLE  |  Prepared 2000–2022 song–artist records')
    ax = canvas(fig)
    box(ax,.02,.62,.24,.23,'Prepared corpus\n6,546 records')
    box(ax,.35,.62,.28,.23,'Automated English\nscreening')
    arrow(ax,(.26,.735),(.35,.735))
    box(ax,.72,.62,.26,.23,'Modelling sample\n6,385 retained', '#E6F3F2')
    arrow(ax,(.63,.735),(.72,.735))
    ax.text(.673,.79,'en',ha='center',fontsize=17)
    box(ax,.35,.08,.28,.23,'161 excluded\nDetector label ≠ en')
    arrow(ax,(.49,.62),(.49,.31))
    box(ax,.72,.30,.26,.18,'984 Top-10\nPeak rank ≤ 10',size=19)
    box(ax,.72,.02,.26,.18,'5,401 other\nPeak rank > 10',size=19)
    arrow(ax,(.79,.62),(.79,.48))
    ax.plot([.99,.99],[.735,.11], color=GRAY,lw=2)
    ax.plot([.98,.99],[.735,.735],color=GRAY,lw=2)
    arrow(ax,(.99,.11),(.98,.11))
    note(fig,'Automated English screening is not verified English-only text; code-switching can remain.\nBox size does not encode quantity. Exclusion applies to modelling only.')
    save(fig,'01_sample_selection')
    guide('01_sample_selection','Actual data','Which records enter the analysis?',
        'Arrows show selection and outcome branches; boxes contain record counts, not proportional areas.',
        'A language detector supplies a provisional label. Retained songs are divided by their observed best chart rank.',
        '“We started with 6,546 prepared records and retained 6,385 under automated English screening. Of these, 984 reached the Top 10 and 5,401 did not.”',
        'The detector can retain multilingual songs; this is not verified English-only text.',
        '`data/processed/billboard_lyrics_corrected_2000_2022.parquet`; `data/processed/stage12_modelling/run_manifest.json`; `reports/topics_and_top10_prediction.md`.')

    songs = ['love love heart day', 'love heart heart day', 'work work money day']
    words = ['love','heart','work','money','day']
    count = np.array([[s.split().count(w) for w in words] for s in songs])
    df = (count > 0).sum(axis=0)
    idf = np.log((1+len(songs))/(1+df))+1
    weighted = count*idf
    tfidf = weighted/np.linalg.norm(weighted,axis=1,keepdims=True)
    assert np.allclose(np.linalg.norm(tfidf,axis=1),1)
    fig = base('How do lyrics become numbers?', 'Teaching illustration — not project data.')
    fig.text(.05,.80,'A. Three invented mini-songs',fontsize=22,weight='bold')
    for i,s in enumerate(songs):
        fig.text(.07,.735-i*.055,f'{i+1}   “{s}”',fontsize=20)
    cmap = LinearSegmentedColormap.from_list('weights',['#FFFFFF','#9BBAD9'])
    for bounds, matrix, heading, fmt, vmax in [([.11,.28,.35,.25], count,'B. Word counts','d',2),
        ([.59,.28,.35,.25],tfidf,'C. Normalized linear TF-IDF','.2f',1)]:
        ax=fig.add_axes(bounds)
        ax.imshow(matrix,cmap=cmap,vmin=0,vmax=vmax,aspect='auto')
        ax.set_xticks(range(5),words); ax.set_yticks(range(3),['Song 1','Song 2','Song 3'])
        ax.tick_params(length=0,pad=10,labelsize=17)
        ax.set_title(heading,pad=20,fontsize=21,loc='left')
        for i in range(3):
            for j in range(5): ax.text(j,i,format(matrix[i,j],fmt),ha='center',va='center',fontsize=22)
        ax.set_xticks(np.arange(-.5,5,1),minor=True);ax.set_yticks(np.arange(-.5,3,1),minor=True)
        ax.grid(which='minor',color=EDGE,lw=1);ax.tick_params(which='minor',length=0)
    note(fig,'Document frequency (df) = number of songs containing a word; “day” has df = 3.\nTF-IDF = count × [1 + ln(4 / (1 + df))], then divide each row by its Euclidean length.\nDarker cells mean larger values within each matrix. Unigrams are single words; order is not represented.')
    save(fig,'02_lyrics_to_numbers')
    guide('02_lyrics_to_numbers','Invented teaching example, with actual calculations','How is text encoded?',
        'Rows are invented songs; columns are words. Left cells are counts (0–2); right cells are TF-IDF weights (0–1); each matrix has its own color scale.',
        'Document frequency counts how many documents contain a word. Linear TF uses the count without logarithmic compression; smoothed IDF is 1 + ln((1+n)/(1+df)); L2 normalization divides by the square root of the sum of squared weights. The common word “day” receives less IDF weight. Rows have unit length, not a sum of one.',
        '“We first count each word in each song. TF-IDF then reduces the relative influence of words found across many songs and normalizes each song’s vector.”',
        'This toy uses no stopwords and retains every word (min_df=1, max_df=1); the project uses min_df=5, max_df=0.95 and a fixed stopword list. Word order is lost.',
        '`src/13_presentation_explainers.py` (invented text and explicit NumPy calculation); `src/12_topics_and_top10_prediction.py` (project representation settings).')

    fig=base('How does NMF make a smaller representation?', 'CONCEPTUAL SCHEMATIC  |  Non-negative matrix factorization; no fitted values shown')
    ax=canvas(fig)
    box(ax,.015,.37,.32,.35,'Song × word matrix\nMany TF-IDF columns\nOne row per song',size=22)
    box(ax,.42,.45,.14,.19,'NMF',fill='#E6F3F2',size=26)
    box(ax,.65,.37,.335,.35,'Song × component matrix\n10 weight columns\nOne row per song',size=22)
    arrow(ax,(.335,.545),(.42,.545));arrow(ax,(.56,.545),(.65,.545))
    ax.text(.5,.18,'Each component is a learned pattern of words that occur together.',ha='center',fontsize=22)
    note(fig,'Component weights are non-negative strengths, not probabilities or song percentages.\nLearn NMF on training songs during validation; the all-data descriptive fit is separate.')
    save(fig,'02b_nmf_representation')
    guide('02b_nmf_representation','Conceptual schematic','What does NMF change?',
        'Boxes show matrix shapes; the arrow reduces many word columns to ten component-weight columns while preserving song rows. No numerical weights are illustrated.',
        'NMF approximates the word matrix with non-negative song weights and component word patterns. A song can have several nonzero weights, without those weights summing to one.',
        '“NMF summarizes the large word table using ten component weights per song. These components can capture repeated vocal sounds as well as recognizable vocabulary themes.”',
        'A component need not be a coherent theme; its weight is not a probability.',
        '`src/12_topics_and_top10_prediction.py`; `reports/topics_and_top10_prediction.md`; `data/processed/stage12_modelling/run_manifest.json`.')

    folds=sorted(oof['validation_fold'].unique().to_list())
    sizes=[oof.filter(pl.col('validation_fold')==f).height for f in folds]
    assert sizes == [x['validation_n'] for x in manifest['folds']]
    fig=base('How are models evaluated on held-out songs?', 'ACTUAL DESIGN  |  Five fixed group partitions, reused for every model')
    ax=fig.add_axes([.15,.30,.70,.47]);ax.set(xlim=(-.5,4.5),ylim=(4.5,-.5))
    for i in range(5):
        for j in range(5):
            held=i==j
            ax.add_patch(Rectangle((j-.5,i-.5),1,1,facecolor=NAVY if held else LIGHT,edgecolor='white',lw=3))
            ax.text(j,i,'Held out' if held else 'Train',ha='center',va='center',fontsize=19,color='white' if held else NAVY)
    ax.set_xticks(range(5),[f'Partition {i+1}\n{n:,} songs' for i,n in enumerate(sizes)])
    ax.set_yticks(range(5),[f'Round {f}' for f in folds]);ax.xaxis.tick_top();ax.tick_params(length=0,pad=12,labelsize=17)
    for spine in ax.spines.values():spine.set_visible(False)
    fig.text(.15,.22,'Learn vocabulary, TF-IDF weights, NMF and classifier on training songs.\nApply the fitted steps to held-out songs.',fontsize=20,linespacing=1.5)
    note(fig,'Columns are groups of songs, not individual songs. Group links include full artist credits and known shared texts.\nComplete-credit grouping leaves collaboration overlap risk; this is not fully unseen-performer evaluation.')
    save(fig,'03_cross_validation')
    guide('03_cross_validation','Actual evaluation design shown schematically','How do we test on songs not used for fitting?',
        'Rows are validation rounds; columns are fixed partitions with saved song counts. Navy cells are held out and light cells train the model; text also identifies each role.',
        'Each song receives a prediction from a model fitted without its partition. Vocabulary, IDF, NMF, numerical preprocessing and the classifier are learned only on training records. All models use the same saved partitions (StratifiedGroupKFold, shuffle=True, random_state=42).',
        '“Each round trains on four partitions and predicts the fifth. Every model gets the same partitions, so comparisons use the same held-out songs.”',
        'Complete-credit groups can separate a performer’s solo and collaboration credits; unknown shared texts and temporal shifts also remain possible.',
        '`data/processed/stage12_modelling/out_of_fold_predictions.csv`; `data/processed/stage12_modelling/run_manifest.json`; `src/12_topics_and_top10_prediction.py`; `reports/topics_and_top10_prediction.md`.')

    fig=base('What do selected lyric components emphasize?', 'ACTUAL SAVED LOADINGS  |  Separate all-data descriptive fit; interpretations are provisional')
    selected=[topics.filter(pl.col('topic')==t).sort('term_rank').head(7) for t in [2,8,9]]
    maxload=max(t['loading'].max() for t in selected)
    for i,(t,label) in enumerate(zip(selected,['Vocal syllables','Attachment vocabulary','Affectionate address'])):
        ax=fig.add_axes([.10+i*.315,.28,.215,.43])
        vals=t['loading'].to_numpy();terms=t['term'].to_list()
        ax.barh(range(7),vals,color=TEAL,height=.63)
        ax.set_yticks(range(7),terms);ax.invert_yaxis();ax.set_xlim(0,maxload*1.20)
        ax.tick_params(axis='y',length=0,labelsize=18);ax.tick_params(axis='x',labelsize=16)
        ax.set_title(f'Component {[2,8,9][i]}\n{label}\n(provisional)',fontsize=19,pad=18)
        ax.set_xlabel('Raw word loading',fontsize=17,labelpad=12)
        for j,v in enumerate(vals):ax.text(v+maxload*.025,j,f'{v:.2f}',va='center',fontsize=15)
        ax.spines[['top','right']].set_visible(False)
    note(fig,'Loading = word importance within a component, not song percentage, prevalence or causal effect.\nNo normalization applied. Component numbers belong to this fit only; do not link them to fold-model coefficients.')
    save(fig,'04_selected_lyric_components')
    guide('04_selected_lyric_components','Actual descriptive model output','Which words characterize three selected components?',
        'Three panels show components 2, 8 and 9; rows are the seven strongest saved words and bars are their raw NMF loadings. All panels share the same zero-based loading scale; teal is a visual accent here.',
        'A larger loading makes a word more prominent within that component. These are provisional patterns from a separate model fitted on all 6,385 eligible records, never used for validation scoring. No displayed loading normalization is applied.',
        '“One component emphasizes vocal syllables, while two others suggest attachment and affectionate address. These labels are provisional interpretations of the highest-loading words.”',
        'Loadings are not song percentages, component prevalence or causal effects; component numbers cannot be linked to classifier coefficients from other fits.',
        '`data/processed/stage12_modelling/descriptive_topics.csv`; `reports/topics_and_top10_prediction.md`; `src/12_topics_and_top10_prediction.py`.')

    ids=[1498,676,369,2160]
    for ident in ids:
        r=src.filter(pl.col('billboard_source_row')==ident).row(0,named=True)
        e=evidence.filter(pl.col('billboard_source_row')==ident).row(0,named=True)
        for field,countfield in [('lyrics','lyric_words_before'),('lyrics_clean','lyric_words_after'),('lyrics_deduplicated','lyric_words_after_dedup')]:
            assert len(r[field].split())==e[countfield]
        if ident in [1498,676]:
            marker=json.loads(e['marker_before_json'])
            assert marker in r['lyrics'].splitlines()
            assert marker.strip() not in [s.strip() for s in r['lyrics_clean'].splitlines()]
        if ident==369:
            clean=r['lyrics_clean'].split();corrected=r['lyrics_deduplicated'].split()
            assert clean == corrected+corrected
        if ident==2160:
            assert r['lyric_language']=='en' and r['lyric_language_mixed_candidate']
            assert re.search('[\uac00-\ud7af]',r['lyrics_deduplicated'])
            assert r['lyrics_clean']==r['lyrics_deduplicated']
    fig=base('What did the historical cleaning actually change?', 'DOCUMENTED EXAMPLES  |  Raw → Stage 10 clean → Stage 11 corrected; counts are whitespace tokens')
    panels=[('Bring Out The Freak In You','Lil Rob','Structural-label cleaning','386 → 375 → 375','[Chorus] → line removed','Seven label lines removed;\nchorus completeness is not established.'),
        ('Animals','Martin Garrix','Standalone music-note removal','10 → 8 → 8','♪ → line removed','Two note-only lines removed;\nuncertain repeated vocals remain.'),
        ('A.M.','One Direction','Supported whole-block correction','642 → 640 → 320','[block A][block A] → [block A]','Block notation is schematic. Only this\nconfirmed case was shortened.'),
        ('DDU-DU DDU-DU','BLACKPINK','Multilingual content retained','316 → 314 → 314','♪ → removed; Korean + Latin text stays','Detector label = en: remained eligible.\nMixed-language flag = true.')]
    for i,(title,artist,kind,nums,trans,detail) in enumerate(panels):
        x=.05+(i%2)*.49;y=.51-(i//2)*.34
        fig.text(x,y+.29,title,fontsize=22,weight='bold')
        fig.text(x,y+.25,artist+'  |  '+kind,fontsize=15,color=GRAY)
        fig.text(x,y+.185,nums,fontsize=26,weight='bold',color=TEAL)
        fig.text(x,y+.125,trans,fontsize=20)
        fig.text(x,y+.035,detail,fontsize=17,linespacing=1.4)
    note(fig,'Historical cleaning examples, not new analytical findings. Stage 11 preserves within-block choruses.\nUncertain encoding problems were flagged, not repaired; these marker examples make no encoding-repair claim.')
    save(fig,'05_actual_cleaning_examples')
    guide('05_actual_cleaning_examples','Documented historical examples; block notation is schematic','What changed, and what was preserved?',
        'Each panel lists raw → clean → corrected whitespace-token counts. These include punctuation-only markers and differ from model tokenizer counts. Marker arrows show removal; [block A] denotes an entire block, not literal source text.',
        'Bring Out The Freak In You: 386→375→375 (seven structural lines removed). Animals: 10→8→8 (two note-only lines removed; uncertain repetition preserved). A.M.: 642→640→320 (two note lines, then one supported duplicated block removed). DDU-DU DDU-DU: 316→314→314 (two note lines removed; Korean/Latin content retained). Local text was read only to verify counts, markers and preservation; no lyric excerpts are exported.',
        '“Cleaning removed documented markers while preserving potentially meaningful text. Only A.M. received the supported whole-block correction, and the multilingual BLACKPINK example remained eligible because its detector label was en.”',
        'Four selected cases do not estimate error prevalence; unresolved encoding issues were not repaired, and structural-label removal does not establish complete chorus coverage.',
        '`reports/lyric_preprocessing_presentation_evidence.csv`; `reports/lyric_preprocessing_2000_2022.md`; `reports/full_block_correction_2000_2022.md`; read-only `data/processed/billboard_lyrics_corrected_2000_2022.parquet`.')

    scores=[]
    for fold in folds:
        sub=oof.filter(pl.col('validation_fold')==fold)
        a=average_precision_score(sub['top10'],sub['audio_probability'])
        c=average_precision_score(sub['top10'],sub['audio_plus_topics_probability'])
        scores.append((a,c))
        for name,score in [('Audio',a),('Audio + topics',c)]:
            assert f'| {fold} | {name} | {score:.4f} |' in report
        assert f'| {fold} | {c-a:+.4f} |' in report
    scores=np.array(scores);deltas=scores[:,1]-scores[:,0]
    assert f'| Mean | {deltas.mean():+.4f} |' in report
    fig=base('Does adding lyric components improve held-out AP?', 'ACTUAL SAVED PREDICTIONS  |  Average precision recomputed within each held-out fold')
    ax=fig.add_axes([.12,.30,.63,.45])
    for i,(a,c) in enumerate(scores):
        ax.plot([a,c],[i,i],color='#ADB9C7',lw=3,zorder=1)
        ax.scatter(a,i,color=BLUE,s=125,marker='o',zorder=3)
        ax.scatter(c,i,color=TEAL,s=130,marker='D',zorder=3)
        ax.text(a,i-.23,f'{a:.4f}',ha='center',fontsize=17,color=BLUE)
        ax.text(c,i+.31,f'{c:.4f}',ha='center',fontsize=17,color=TEAL)
        ax.text(1.08,i,f'{c-a:+.4f}',transform=ax.get_yaxis_transform(),va='center',fontsize=21)
    ax.set(yticks=range(5),yticklabels=[f'Fold {f}' for f in folds],ylim=(4.65,-.65),xlim=(.195,.28))
    ax.set_xlabel('Average precision (AP) — higher is better',fontsize=20,labelpad=16)
    ax.set_xticks([.20,.22,.24,.26,.28]);ax.grid(axis='x',color=LIGHT);ax.spines[['top','right']].set_visible(False)
    fig.text(.12,.80,'● Audio',fontsize=21,color=BLUE);fig.text(.28,.80,'◆ Combined: audio + topics',fontsize=21,color=TEAL)
    fig.text(.80,.80,'Δ combined − audio',fontsize=17)
    fig.text(.12,.155,f'Equal-fold means: audio {scores[:,0].mean():.4f}  |  combined {scores[:,1].mean():.4f}  |  difference {deltas.mean():+.4f}',fontsize=22,weight='bold')
    note(fig,'Focused x-axis (0.195–0.280). AP summarizes precision across recall increments; it is not accuracy.\nFold variation is descriptive: folds share training songs and are not independent replicates for a simple significance test.')
    save(fig,'06_paired_fold_results')
    scoretext='; '.join(f'fold {i+1}: {a:.6f} → {c:.6f} (Δ {c-a:+.6f})' for i,(a,c) in enumerate(scores))
    guide('06_paired_fold_results','Actual evaluation results recomputed from saved predictions','Does combined beat audio on the same held-out songs?',
        'Rows are folds; x is average precision. Blue circles are audio; teal diamonds are audio plus ten lyric components. A connector pairs the scores; right labels are combined minus audio. The axis is deliberately focused at 0.195–0.280.',
        'AP rewards placing Top-10 songs high in the score ranking: it sums precision weighted by increases in recall. It is not classification accuracy or trapezoidal PR-AUC. Means weight the five folds equally, rather than pooling all predictions. '+scoretext+'.',
        '“The combined model had higher average precision in all five saved folds. Its mean AP was 0.2527 versus 0.2334 for audio, a paired mean difference of 0.0193.”',
        'Folds share training songs and are not independent replicates for a simple significance test; this is neither a significance nor a causal claim.',
        '`data/processed/stage12_modelling/out_of_fold_predictions.csv`; verified to the reported precision against `reports/topics_and_top10_prediction.md`; `src/13_presentation_explainers.py` uses `sklearn.metrics.average_precision_score` without refitting.')

    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in hashes.items())
    header='# Presentation visual guide\n\nAll images are 1920×1080 PNG plus editable-text SVG, in this directory. '
    header+='Run `python src/13_presentation_explainers.py` using the existing project environment to reproduce them. '
    header+='No upstream cleaning, review, integration or project model fitting is run. Existing inputs and results are read-only.\n\n'
    header+='For a 12-minute main presentation, use 01, 02, 03 and 06 (sample → representation → evaluation → findings). '
    header+='Keep 02b, 04 and 05 as appendix material.\n\n'
    footer='\n## Verification\n\nThe script checks sample counts against saved metadata and the corrected corpus, unique OOF records and targets, '
    footer+='saved partition sizes and group separation, all displayed AP values/differences against the existing report, '
    footer+='and four cleaning examples against local text. Toy TF-IDF is explicitly calculated with unit-length rows. '
    footer+='Input hashes are unchanged before/after generation. PNG and SVG use the same fixed 16:9 layout; text extents are checked against the canvas.\n'
    (OUT/'visual_guide.md').write_text(header+'\n'.join(GUIDE)+footer,encoding='utf-8')
    print('Created 7 figure pairs and visual_guide.md; counts, AP, cleaning examples and input preservation checks passed.')


if __name__ == '__main__':
    main()
