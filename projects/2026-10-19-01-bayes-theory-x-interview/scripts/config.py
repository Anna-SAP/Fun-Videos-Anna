# -*- coding: utf-8 -*-
"""Edit decision list for 「非常贝叶斯 · 理论解析 + 访谈实录」.

T* = theory segments from 非常贝叶斯.mp4 (narration backbone)
E* = evidence inserts from clip_贝叶斯.mp4 (original interview, burned-in EN captions)
All times are seconds in the source file.
"""

FPS = 30
W, H = 1080, 1920

THEORY = "非常贝叶斯.mp4"
CLIP = "clip_贝叶斯.mp4"

# clip crop (YouTube screen recording): picture + caption band, without player chrome
CLIP_CROP = (1728, 1010, 96, 54)          # w, h, x, y
PANEL = (40, 330, 1000, 584)               # x, y, w, h of the video panel in the 1080x1920 frame
# YouTube player UI visible in source 1.05–4.65 s -> mask (coords inside the crop)
UI_WINDOWS = [(1.05, 4.65)]
UI_BAND = (0, 954, 1728, 56)               # progress bar + controls row
UI_ICONS = (1480, 898, 232, 52)            # like / dislike / comment / share icons

# ---------------------------------------------------------------- captions (clip, absolute)
CAP = {
 "L1":  (0.00, 1.25, "How is Mark a different boss than you expected?", "Mark 当老板，和你预想的有什么不同？", []),
 "L2":  (2.25, 4.30, "Um, well, I don't have a huge comparison set.", "嗯……我能拿来比较的样本其实不多。", ["huge comparison set"]),
 "L3":  (4.75, 6.45, "I think I can leave now. Yeah, exactly.", "我想我现在可以先走了。——对，没错。", []),
 "L6":  (16.05, 20.55, "one of the very cool things about like working with Mark over the past year", "过去一年和 Mark 共事，最酷的事情之一，", []),
 "L7":  (21.25, 26.42, "has just been watching like the true degree of his boldness", "就是亲眼见识到他的魄力究竟有多大。", ["boldness"]),
 "L9":  (29.75, 36.05, "once he internalizes certain beliefs, like the— speed and magnitude of willing", "一旦他内化了某些信念——那种速度和力度，", ["speed and magnitude"]),
 "L10": (36.50, 42.80, "to change prior actions and pivot towards the worldview that is", "他愿意改变先前的做法，转向一个", ["change prior actions", "pivot"]),
 "L11": (43.00, 44.05, "consistent with those beliefs.", "与这些信念相一致的世界观。", []),
 "L12": (44.50, 49.80, "I think these are pretty unusual traits, generally speaking, even", "总的来说，我觉得这些特质相当少见，", ["pretty unusual traits"]),
 "L13": (50.50, 52.30, "among this base of founders.", "即便放在创始人群体里也是如此。", ["founders"]),
 "L14": (52.50, 56.05, "Mark actually ingests new information and fully updates his worldview and then", "Mark 会真正吸收新信息、全面更新世界观，", ["ingests new information", "fully updates his worldview"]),
 "L15": (56.25, 58.12, "acts in accordance with the newly installed worldview.", "然后按照新“装好”的世界观去行动。", ["newly installed"]),
 "L16": (58.75, 61.55, "Very Bayesian. And then willing to take— Very Bayesian.", "非常贝叶斯。——然后愿意去……\n——非常贝叶斯。", ["Very Bayesian"]),
 "L17": (62.25, 64.30, "Very Bayesian. I've never gotten such a nice compliment.", "非常贝叶斯。我还从没收到过这么好的夸奖。", ["Very Bayesian"]),
 "L18": (65.25, 67.80, "What lovely priors you have.", "你的先验（priors）可真不错。", ["priors"]),
 "L19": (68.75, 70.05, "Yeah. Posterior.", "对。Posterior（后验）。", ["Posterior"]),
 "L20": (70.50, 73.05, "You're not allowed to talk about posteriors anymore after", "你可不能再聊 posterior 了，自从……", ["posteriors"]),
 "L21": (73.25, 75.02, "the whole incident. Yeah.", "……出了那件事之后。没错。", []),
}

# ---------------------------------------------------------------- evidence inserts
EVIDENCE = {
 "E1": dict(src=(0.07, 6.45), afade=(0.05, 0.35), caps=["L1", "L2", "L3"], anno_at=2.35,
            heading="开场：先给判断加个{限定}",
            keys=[("comparison set", "可供比较的样本")],
            note="先交代“样本有限”，等于提醒观众：下面是共事中的一手观察，不是统计结论，证据分量要打个折。"),
 "E2": dict(src=(15.65, 26.42), afade=(0.08, 0.06), caps=["L6", "L7"], anno_at=5.6,
            heading="“极具{魄力}”的原话：boldness",
            keys=[("boldness", "魄力 / 胆识")],
            note="解析里的“极具魄力”有原话支撑——而且来自共事一年的近距离观察。"),
 "E3": dict(src=(29.98, 44.05), afade=(0.06, 0.06), caps=["L9", "L10", "L11"], anno_at=6.6,
            heading="“推翻过往、{迅速掉头}”的原话",
            keys=[("speed and magnitude", "速度与幅度"), ("change prior actions", "改变先前的做法"), ("pivot", "掉头 / 转向")],
            note="留意 prior 这个词：这里它只是“之前的”，到了对话结尾，它会以“先验”的身份再次登场。"),
 "E4": dict(src=(44.10, 58.12), afade=(0.05, 0.08), caps=["L12", "L13", "L14", "L15"], anno_at=8.4,
            heading="“吸收新信息、{刷新世界观}”的原话",
            keys=[("ingests new information", "吸收新信息"), ("fully updates his worldview", "全面更新世界观"), ("newly installed", "新“安装”的")],
            note="ingest（摄入）、install（安装）都是机器式的比喻——解析里“像机器一样吸收、刷新”正对应这里。"),
 "E5": dict(src=(58.15, 64.60), afade=(0.08, 0.30), caps=["L16", "L17"], anno_at=0.6,
            heading="“{Very Bayesian}”出现的瞬间",
            keys=[("Very Bayesian", "非常贝叶斯")],
            note="“吸收新信息 → 更新世界观 → 照此行动”刚说完，现场就用一个统计学词给它下了定义。"),
 "E6": dict(src=(64.90, 75.02), afade=(0.20, 0.10), caps=["L18", "L19", "L20", "L21"], anno_at=3.85,
            heading="双关现场：从 {prior} 到 {posterior}",
            keys=[("priors", "先验：看到证据前的信念"), ("posterior", "后验 —— 也可指“臀部”")],
            note="从 priors 顺势接一句 posterior，统计术语秒变“屁股梗”——笑点就在这里。"),
}

# ---------------------------------------------------------------- theory segments
THEORY_SEG = {
 "T1": dict(src=(0.00, 13.62)),   # 钩子 + 方法：为什么硅谷大佬……和美式幽默。
 "T2": dict(src=(13.62, 16.40)),  # 嘉宾首先感叹扎克伯格极具魄力。
 "T3": dict(src=(16.40, 20.60)),  # 一旦接纳新理念，他就能果断推翻过往，迅速掉头。
 "T4": dict(src=(20.60, 26.95)),  # 也就是像机器一样，大口“吸收”新信息，并据此彻底“刷新”自己的世界观。
 "T5": dict(src=(26.95, 31.20)),  # 这种特质，被精确总结为“非常贝叶斯”。
 "T6": dict(src=(31.20, 38.10), note_at=0.9),  # 核心奥义：不死守偏见，根据新证据修正判断（+严谨注）
 "T7": dict(src=(38.10, 50.60)),  # 对话结尾的双关：prior / posterior / 臀部
 "T8": dict(src=(50.60, 63.60)),  # 这就是为什么大家会哄堂大笑 + 升华（去掉 Gemini 片尾）
}

ORDER = ["T1", "E1", "T2", "E2", "T3", "E3", "T4", "E4", "T5", "E5", "T6", "T7", "E6", "T8", "END"]
END_DUR = 2.8

T6_NOTE = ("严谨注", "Prior（先验）＝看到新证据之前的信念，不等于“偏见”；Posterior（后验）＝结合新证据之后的信念。")

FOOTNOTE = "素材：Zuckerberg's $100 Billion Bet 访谈片段（英文原字幕）"
