# Teaching guidelines — the research behind them

lezio does not have fixed visual styles: for every segment the agent decides how to teach it, following
**guidelines** drawn from research on multimedia learning and educational video. This document collects
that research (October 2026) with its sources and how strong the evidence is. The agent receives a
condensed, operational version: `src/lezio/agent/prompts/rules/teaching.md`. Keep the two in sync.

The guidelines are defaults, not rules. The user's instructions override them, and the depth setting
decides how much is added to the material.

**Evidence strength**: **strong** = several meta-analyses or a broad consensus · **moderate** = one
meta-analysis or several experiments · **limited** = one study, observational data or theory · *practice*
= what good explainers do, untested.

## Two things to keep in mind

- **Effect sizes vary a lot.** Mayer's own medians (short lessons, university students, immediate tests)
  are much larger than those of independent meta-analyses, which mostly find g ≈ 0.2–0.45. Read numbers as
  priorities, not predictions (Mayer 2024; Noetel et al. 2022).
- **The principles matter most where lezio works.** They matter more for complex material (g = 0.70 vs
  0.20) and for system-paced media such as videos (0.41 vs 0.27), and mostly for learners with **low prior
  knowledge**. Almost every kind of guidance becomes useless, or even harmful, for experts: this is the
  expertise reversal effect (Noetel et al. 2022; Kalyuga et al. 2003).

## 1. Words and pictures

| Finding | Evidence |
|---|---|
| Words + pictures beat words alone (*multimedia*) | strong (Mayer 2021; Noetel 2022) |
| Speech + graphics beats on-screen text + graphics (*modality*). The effect is smaller after correcting for publication bias (g = 0.20), and it **reverses for long spoken texts** | moderate (Reinwein 2012 via Noetel; Leahy & Sweller 2011, 2016) |
| On-screen text that repeats the narration hurts when there are pictures. **2–3-word key terms** placed next to the part of the diagram they name help retention (d = 0.47/0.70) | moderate (Adesope & Nesbit 2012; Mayer & Johnson 2008) |
| Words and pictures integrated **in space** (labels on the parts) | strong, g = 0.63 (Schroeder & Cenkci 2018) |
| Words and pictures integrated **in time** (shown when spoken) | strong, g = 0.78 (Ginns 2006) |
| **Transient information**: speech, animation and video disappear, so they load working memory. Remedies: short segments, a permanent written version of what must be held | moderate (Leahy & Sweller 2011; Singh et al. 2012; Jiang & Sweller 2022; Castro-Alonso et al. 2021) |

→ The voice explains and the screen shows. On screen go key terms, labels on the parts, formulas, numbers and
the problem statement, kept visible as long as they are used. Narration pieces are short.

## 2. Signaling, coherence, segmenting

| Finding | Evidence |
|---|---|
| **Signaling** (highlight what is being discussed; verbal cues such as "first", "three steps") | strong, g = 0.43, k = 209 (Schneider et al. 2018); r = .17 for text–picture links, mainly for novices (Richter et al. 2016) |
| **Color-coding** a concept the same in text and picture; changing an element's color when the voice names it | moderate (Ozcelik et al. 2009; Jamet et al. 2008) |
| **Coherence**: cut extraneous material. Seductive details hurt (g = −0.33), more when they **stay on screen** (0.43 vs 0.12 when brief) | strong (Sundararajan & Adesope 2020; Harp & Mayer 1998) |
| Decorative pictures give about zero gain; pictures with a function (representational, organizational, interpretive, transformational) help | strong (Levin, Anglin & Carney 1987; Carney & Levin 2002) |
| **Segmenting**: short units with clear boundaries, set by the system or instructor | strong, g = 0.34, k = 123; 0.41 when system-set (Rey et al. 2019); pauses and boundary cues both help (Spanjers et al. 2012) |
| **Pre-training**: names and parts first, then the mechanism | moderate (Mayer 2021; no meta-analysis) |
| **Isolated elements**: very interconnected material → elements one at a time, then their interactions | moderate (Pollock, Chandler & Sweller 2002) |

## 3. Choosing the representation

| Finding | Evidence |
|---|---|
| A diagram groups together the information that is used together and lets relations be read by eye, but only for viewers who can read that kind of diagram | strong theory (Larkin & Simon 1987) |
| Multiple representations help when they complement or constrain each other, but novices rarely link them on their own: show the links | moderate (Ainsworth 2006) |
| **Animation vs static pictures**: a small overall benefit (d = 0.37; g = 0.23). It is larger for realistic or procedural content and when narrated and system-paced. Decorative animation: g ≈ 0 | strong (Höffler & Leutner 2007; Berney & Bétrancourt 2016) |
| Animation helps when the **change itself** is what must be learned (trajectory, manner, timing): the *congruence* principle. It is often too fast to perceive (*apprehension*). Annotated static frames matched or beat narrated animations in 4 experiments | moderate (Tversky, Morrison & Bétrancourt 2002; Ploetzner et al. 2020, 2021; Mayer, Hegarty et al. 2005) |
| Building a complex animation part by part, then the relations, with cues | moderate (Lowe & Boucheix, composition approach) |
| **Drawing while explaining** beats showing the finished diagram (d = 0.54 with no instructor visible). The gain comes from the synchronized build-up; animated drawing without a hand was not significant | moderate, one lab (Fiorella & Mayer 2016; Fiorella et al. 2019) |
| Khan-style drawing videos kept viewers 1.5–2× longer than slides | limited, engagement only (Guo, Kim & Rubin 2014) |
| A bland diagram transferred better than a detailed, realistic one (realism helps motor procedures) | limited/mixed (Menendez et al. 2020; Scheiter et al. 2009) |
| Tables for exact values; line charts for trends; bars for discrete comparisons; position on a common scale is read most accurately | strong/moderate (Vessey 1991; Zacks & Tversky 1999; Cleveland & McGill 1984) |

## 4. Examples, analogies, comparisons, misconceptions

| Finding | Evidence |
|---|---|
| **Worked examples** beat problem solving for novices (g = 0.48 in mathematics). They work when each step is explained ("why"), steps are grouped under **subgoal labels**, and they fade toward problems; the benefit reverses with expertise | strong (Atkinson et al. 2000; Barbieri et al. 2023; Renkl 2014; Catrambone 1998; Renkl, Atkinson et al. 2002; Kalyuga et al. 2003) |
| Example → similar problem works; problem → example does not beat problems alone | moderate (van Gog, Kester & Paas 2011) |
| **Concreteness fading**: concrete → iconic → abstract, with explicit links | moderate/limited (Fyfe et al. 2014) |
| **Analogies** work with a familiar source, shown side by side with the target, aligned, with explicit links | moderate (Gentner et al. 2003; Richland et al. 2007; Richland & McDonough 2010; Richland & Simms 2015) |
| **Comparing cases** shown at the same time (d ≈ 0.5); state the principle after the comparison; for concepts, examples paired with non-examples that differ only in the critical feature | strong/moderate (Alfieri et al. 2013; Rittle-Johnson & Star 2007; Tennyson & Park 1980) |
| **Refuting misconceptions** beats clear exposition (d ≈ 0.8). Viewers rated the exposition "clear" yet learned little; fluent delivery raises perceived learning, not learning | strong (Muller et al. 2008 ×2; Danielson et al. 2025; Carpenter et al. 2013) |
| Problem before explanation helps conceptual knowledge (g = 0.36) | moderate; extrapolated to video (Sinha & Kapur 2021) |

## 5. Engagement, questions, narration

| Finding | Evidence |
|---|---|
| **Questions inside the video** (retrieval after each part): mind wandering halved, final recall much higher (d ≈ 1). This was not replicated in a 52-minute lecture. Retrieval practice in general is robust | strong for retrieval in general; contested in video (Szpunar et al. 2013; Jing et al. 2016; Welhaf et al. 2022; Yang et al. 2021; Adesope et al. 2017) |
| **Pre-questions** and curiosity direct attention; in long lectures the benefit is limited to the content asked about | moderate, mixed (Carpenter & Toftness 2017; Toftness et al. 2018; Pan et al. 2020; Gruber et al. 2014) |
| **Generative prompts** (explain, summarize after each part) | moderate, d = .87 on transfer (Fiorella et al. 2020) |
| **Conversational style** ("you", "we"); the benefit shrinks in lessons over about 35 minutes | moderate (Ginns, Martin & Marsh 2013) |
| A modern TTS voice was about as good as a human voice; robotic voices hurt. An instructor shown on screen adds little | limited/moderate (Craig & Schroeder 2017/2019; Mayer 2021 image principle) |
| Enthusiasm helps; a monotone delivery does not | moderate (Lawson et al. 2021; Guo et al. 2014) |
| A narrative arc (question → tension → resolution) is understood and recalled better | moderate, with confounds (Mar et al. 2021) |
| An advance organizer or roadmap gives a small benefit | moderate (Luiten et al. 1980) |
| Videos of about **6 minutes** keep viewers watching. This concerns engagement, not learning, and motivated students watch longer | limited (Guo et al. 2014; Lagerstrom et al. 2015) |
| Speaking fast or speeding up: contradictory results | contested (Murphy et al. 2022; Huang et al. 2025) |
| Spacing within one video: weak | strong in general, weak here (Cepeda et al. 2006) |

## How lezio uses them

- **Plan**:
  - the order of the lesson: opening question and roadmap, why before how, parts before mechanisms, concrete before abstract;
  - one idea per segment;
  - a **visual language** for the whole lesson: one color and symbol per concept, used in every segment;
  - the main visual idea of each segment.
- **Write**: the representation chosen per segment, the build-up synchronized with the voice, signaling, short labels and pieces, questions with pauses, recaps that ask.
- **Review**: the final frames are checked against the same guidelines.
- **What only the program does**:
  - one voice;
  - no decorative effects or music;
  - **themes** keep colors and fonts consistent;
  - the narration format allows pauses for thinking (`"pause": 3`);
  - the depth bounds how much is added to the material.

## Sources

- Adesope & Nesbit 2012, *Verbal redundancy in multimedia learning environments*, J. Educ. Psych. 104 — https://doi.org/10.1037/a0026147
- Adesope, Trevisan & Sundararajan 2017, *Rethinking the use of tests*, Rev. Educ. Res. 87:659
- Ainsworth 2006, *DeFT: A conceptual framework for considering learning with multiple representations*, Learning & Instruction 16 — https://doi.org/10.1016/j.learninstruc.2006.03.001
- Alfieri, Nokes-Malach & Schunn 2013, *Learning through case comparisons*, Educ. Psychologist 48 — https://files.eric.ed.gov/fulltext/ED528947.pdf
- Atkinson, Derry, Renkl & Wortham 2000, *Learning from examples*, Rev. Educ. Res. 70
- Barbieri et al. 2023, worked examples in mathematics (meta-analysis), Educ. Psych. Review
- Berney & Bétrancourt 2016, *Does animation enhance learning? A meta-analysis* — https://archive-ouverte.unige.ch/unige:92234
- Brame 2016, *Effective educational videos*, CBE-Life Sci. Educ. 15:es6 — https://pmc.ncbi.nlm.nih.gov/articles/PMC5132380/
- Carney & Levin 2002, *Pictorial illustrations still improve students' learning from text*, Educ. Psych. Review 14 — https://doi.org/10.1023/A:1013176309260
- Carpenter et al. 2013, *Appearances can be deceiving: instructor fluency…*, Psychon. Bull. Rev.
- Carpenter & Toftness 2017, *The effect of prequestions on learning from video presentations*, JARMAC 6:104
- Castro-Alonso et al. 2021, *Five strategies for optimizing instructional materials*, Educ. Psych. Review — https://doi.org/10.1007/s10648-021-09606-9
- Catrambone 1998, *The subgoal learning model*, J. Exp. Psych.: General
- Cepeda et al. 2006, *Distributed practice in verbal recall tasks*, Psych. Bulletin 132:354
- Cleveland & McGill 1984, *Graphical perception*, JASA
- Craig & Schroeder 2017/2019, modern TTS vs human voice — https://doi.org/10.1177/0735633118802877
- Danielson et al. 2025, refutation texts (meta-analysis), Educ. Psychologist 60(1)
- Fiorella & Mayer 2016, *Effects of observing the instructor draw diagrams*, J. Educ. Psych. 108 — https://doi.org/10.1037/edu0000065
- Fiorella, Stull, Kuhlmann & Mayer 2019, *Instructor presence in video lectures*, J. Educ. Psych. 111:1162
- Fiorella et al. 2020, *Fostering generative learning from video lessons*, J. Educ. Psych. 112:895
- Fyfe, McNeil, Son & Goldstone 2014, *Concreteness fading in mathematics and science instruction*, Educ. Psych. Review 26 — https://doi.org/10.1007/s10648-014-9249-3
- Gentner, Loewenstein & Thompson 2003, *Learning and transfer: a general role for analogical encoding*, J. Educ. Psych.
- Ginns 2006, *Integrating information: a meta-analysis of spatial and temporal contiguity*, Learning & Instruction 16
- Ginns, Martin & Marsh 2013, *Designing instructional text in a conversational style*, Educ. Psych. Review 25:445
- Gruber, Gelman & Ranganath 2014, *States of curiosity modulate hippocampus-dependent learning*, Neuron — https://pmc.ncbi.nlm.nih.gov/articles/PMC4252494/
- Guo, Kim & Rubin 2014, *How video production affects student engagement*, L@S — https://doi.org/10.1145/2556325.2566239
- Harp & Mayer 1998, *How seductive details do their damage*, J. Educ. Psych. 90:414
- Höffler & Leutner 2007, *Instructional animation versus static pictures: a meta-analysis*, Learning & Instruction 17
- Jamet, Gavota & Quaireau 2008, *Attention guiding in multimedia learning*, Learning & Instruction 18
- Jiang & Sweller 2022, *Transient information principle*, Cambridge Handbook of Multimedia Learning
- Kalyuga, Ayres, Chandler & Sweller 2003, *The expertise reversal effect*, Educ. Psychologist 38 — https://doi.org/10.1207/S15326985EP3801_4
- Kim et al. 2014, *Understanding in-video dropouts and interaction peaks*, L@S — https://dspace.mit.edu/handle/1721.1/90413
- Lagerstrom, Johanes & Ponsukcharoen 2015, *The myth of the six-minute rule*, ASEE — https://peer.asee.org/24895
- Larkin & Simon 1987, *Why a diagram is (sometimes) worth ten thousand words*, Cognitive Science 11
- Lawson et al. 2021, *The positivity principle*, ETR&D — https://link.springer.com/article/10.1007/s11423-021-10057-w
- Leahy & Sweller 2011, *Cognitive load theory, modality of presentation and the transient information effect*, Applied Cognitive Psych. 25 — https://doi.org/10.1002/acp.1787
- Levin, Anglin & Carney 1987, *On empirically validating functions of pictures in prose*
- Lowe & Boucheix, *Principled animation design improves comprehension of complex dynamics* — https://lead.ube.fr/wp-content/uploads/2023/09/001168-principled-animation-design-improves-comprehension-of-complex-dynamics.pdf
- Mar et al. 2021, *Memory and comprehension of narrative versus expository texts: a meta-analysis*, Psychon. Bull. Rev. 28 — https://pmc.ncbi.nlm.nih.gov/articles/PMC8219577/
- Mayer 2021, *Multimedia Learning* (3rd ed.); Mayer 2024, Educ. Psych. Review 36:8 — https://doi.org/10.1007/s10648-023-09842-1
- Mayer, Fiorella & Stull 2020, *Five ways to increase the effectiveness of instructional video*, ETR&D 68 — https://doi.org/10.1007/s11423-020-09749-6
- Mayer, Hegarty, Mayer & Campbell 2005, *When static media promote active learning*, J. Exp. Psych.: Applied 11
- Mayer & Johnson 2008, *Revising the redundancy principle*, J. Educ. Psych. — https://doi.org/10.1037/0022-0663.100.2.380
- Menendez, Rosengren & Alibali 2020, *Do details bug you?* — https://rosengrenlab.digitalscholar.rochester.edu/wp-content/uploads/2021/05/MenendezRosengrenAlibali2020DoDetails-Bug-You.pdf
- Muller, Bewes, Sharma & Reimann 2008, *Saying the wrong thing*, J. Computer Assisted Learning 24:144; Muller, Sharma & Reimann 2008, Science Education 92:278
- Noetel et al. 2022, *Multimedia design for learning: an overview of reviews*, Rev. Educ. Res. 92(3) — https://doi.org/10.3102/00346543211052329
- Ozcelik, Karakus, Kursun & Cagiltay 2009, color coding — https://open.metu.edu.tr/handle/11511/28595
- Ploetzner, Berney & Bétrancourt 2021, *When learning from animations is more successful than learning from static pictures*, Instructional Science — https://link.springer.com/article/10.1007/s11251-021-09541-w
- Pollock, Chandler & Sweller 2002, *Assimilating complex information*, Learning & Instruction 12
- Renkl 2014, *Toward an instructionally oriented theory of example-based learning*, Cognitive Science 38
- Rey et al. 2019, *A meta-analysis of the segmenting effect*, Educ. Psych. Review 31:389 — https://doi.org/10.1007/s10648-018-9456-4
- Richland, Zur & Holyoak 2007, *Cognitive supports for analogies in the mathematics classroom*, Science — https://pubmed.ncbi.nlm.nih.gov/17525320; Richland & Simms 2015 — https://learninglab.uchicago.edu/Publications_files/Richland%26Simms_WIREs.pdf
- Richter, Scheiter & Eitel 2016, *Signaling text-picture relations*, Educ. Res. Review 17 — https://doi.org/10.1016/j.edurev.2015.12.003
- Rittle-Johnson & Star 2007, *Does comparing solution methods facilitate conceptual and procedural knowledge?*, J. Educ. Psych.
- Schneider, Beege, Nebel & Rey 2018, *A meta-analysis of how signaling affects learning*, Educ. Res. Review — https://doi.org/10.1016/j.edurev.2017.11.001
- Schroeder & Cenkci 2018, *Spatial contiguity and spatial split-attention effects*, Educ. Psych. Review — https://doi.org/10.1007/s10648-018-9435-9
- Singh, Marcus & Ayres 2012, transient information and segmenting — https://doi.org/10.1002/acp.2885
- Sinha & Kapur 2021, *When problem solving followed by instruction works*, Rev. Educ. Res.
- Spanjers et al. 2012, segmenting animations — https://repub.eur.nl/pub/70813
- Sundararajan & Adesope 2020, *Keep it coherent: a meta-analysis of the seductive details effect*, Educ. Psych. Review 32 — https://doi.org/10.1007/s10648-020-09522-4
- Sweller, van Merriënboer & Paas 2019, *Cognitive architecture and instructional design: 20 years later*, Educ. Psych. Review 31 — https://doi.org/10.1007/s10648-019-09465-5
- Szpunar, Khan & Schacter 2013, *Interpolated memory tests reduce mind wandering*, PNAS 110 — https://doi.org/10.1073/pnas.1221764110
- Tennyson & Park 1980, *The teaching of concepts*, Rev. Educ. Res.
- Tversky, Morrison & Bétrancourt 2002, *Animation: can it facilitate?*, Int. J. Human-Computer Studies — https://hci.stanford.edu/courses/cs448b/papers/Tversky_AnimationFacilitate_IJHCS02.pdf
- van Gog, Kester & Paas 2011, *Effects of worked examples, example-problem, and problem-example pairs* — https://repub.eur.nl/pub/26205
- Vessey 1991, *Cognitive fit*, Decision Sciences
- Welhaf et al. 2022, interpolated testing in a long lecture, Cognitive Research — https://pmc.ncbi.nlm.nih.gov/articles/PMC8964911/
- Yang et al. 2021, *Testing (quizzing) boosts classroom learning*, Psych. Bulletin
- Zacks & Tversky 1999, *Bars and lines: a study of graphic communication*, Memory & Cognition — https://link.springer.com/content/pdf/10.3758/bf03201236.pdf
