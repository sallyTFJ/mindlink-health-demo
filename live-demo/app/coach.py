"""Conservative multimodal support logic for MindLink.

The signal models in this package are research estimates.  This module never
labels anxiety, depression, mania, violence risk, or any other diagnosis.  It
only turns fresh signal changes and explicit self-reports into low-risk support
prompts.  Urgent guidance can only be triggered by the person's own check-in.
"""

from __future__ import annotations

import copy
import statistics
import threading
import time
from collections import deque


CHECK_IN_TTL_SECONDS = {
    "tense": 15 * 60,
    "overwhelmed": 20 * 60,
    "unsafe": 30 * 60,
    "task_complete": 5 * 60,
    "calm": 10 * 60,
}


class SupportCoach:
    """Keeps a short local baseline and produces an explainable support state."""

    def __init__(self):
        self.lock = threading.RLock()
        self.check_in_event = None
        self.hr_baseline = deque(maxlen=180)
        self.evidence = deque(maxlen=12)
        self.last_evidence_id = None

    def check_in(self, kind, note="", now=None):
        if kind not in CHECK_IN_TTL_SECONDS:
            raise ValueError("check-in must be calm, tense, overwhelmed, unsafe or task_complete")
        if not isinstance(note, str) or len(note) > 280:
            raise ValueError("note must be a string up to 280 characters")
        event = {"kind": kind, "note": note.strip(), "at": time.time() if now is None else float(now)}
        with self.lock:
            self.check_in_event = event
        return copy.deepcopy(event)

    @staticmethod
    def _base(level, title, message, voice, actions, basis=(), confidence="low"):
        return {
            "level": level,
            "title": title,
            "message": message,
            "voice_text": voice,
            "actions": list(actions),
            "signal_basis": list(basis),
            "confidence": confidence,
            "can_diagnose": False,
            "medical_disclaimer": "这是趋势陪伴提示，不是对焦虑、抑郁、躁狂、癫痫或伤害风险的诊断。",
            "stimulation": {
                "automatic_control": False,
                "available": False,
                "guidance": "系统不会自动启动或设置任何电刺激。仅可在专业人员指导下，按合规设备说明由本人主动操作。",
            },
        }

    def _active_check_in(self, now):
        event = self.check_in_event
        if not event:
            return None
        if now - event["at"] > CHECK_IN_TTL_SECONDS[event["kind"]]:
            return None
        return event

    def assess(self, state, now=None):
        now = time.time() if now is None else float(now)
        heart = state.get("heart_rate") or {}
        brain = state.get("brain_state") or {}
        with self.lock:
            check_in = self._active_check_in(now)

            if check_in and check_in["kind"] == "unsafe":
                return self._base(
                    "urgent",
                    "现在先把安全放在第一位",
                    "信号无法判断伤害风险，但你刚才的反馈值得立即获得真人支持。请不要独处，并远离可能造成伤害的物品。",
                    "谢谢你告诉我。现在先不要一个人扛着。请联系身边可信任的人，让对方陪着你；如果危险正在发生，请立即联系当地紧急援助。",
                    ["联系一位可信任的人并请对方陪伴", "离开危险环境并远离可能造成伤害的物品", "如危险正在发生，立即联系当地紧急援助"],
                    ["用户主动选择“我现在不安全”"],
                    "self_report",
                )

            if check_in and check_in["kind"] in ("tense", "overwhelmed"):
                overwhelmed = check_in["kind"] == "overwhelmed"
                return self._base(
                    "pause" if overwhelmed else "notice",
                    "先让这一分钟慢下来",
                    "谢谢你如实反馈。现在不需要解决全部问题，先把注意力放在脚底触地和缓慢呼气上。",
                    "我在。先把肩膀放松一点，缓慢呼气六秒，再自然吸气四秒。我们只做三轮，不急着解决所有事情。",
                    ["做 3 轮 4 秒吸气、6 秒呼气", "喝一口水并离开屏幕 2 分钟", "若仍无法缓解，联系可信任的人或专业人员"],
                    ["用户主动反馈紧绷或难以舒缓"],
                    "self_report",
                )

            if check_in and check_in["kind"] == "task_complete":
                return self._base(
                    "celebrate",
                    "这件难事，你完成了",
                    "完成艰难任务值得被看见。把这一刻记下来，它会成为下一次出发时可以调用的证据。",
                    "做得很好。你刚刚完成了一件不容易的事。先停十秒，感受一下自己已经做到的部分。",
                    ["记录一句“我刚刚做到了什么”", "给自己 30 秒不带条件的肯定", "补水并短暂走动"],
                    ["用户主动标记任务完成"],
                    "self_report",
                )

            bpm = heart.get("bpm") if heart.get("valid") else None
            valence = brain.get("valence_score") if brain.get("valid") else None
            attention = brain.get("attention_score") if brain.get("valid") else None
            evidence_id = (heart.get("event_id"), brain.get("sample_time_end_unix_s"))

            if evidence_id != self.last_evidence_id and any(v is not None for v in evidence_id):
                if isinstance(bpm, (int, float)):
                    self.hr_baseline.append(float(bpm))
                baseline = statistics.median(self.hr_baseline) if len(self.hr_baseline) >= 10 else None
                hr_delta = float(bpm) - baseline if baseline is not None and bpm is not None else None
                score = 0
                basis = []
                if hr_delta is not None and hr_delta >= 15:
                    score += 1
                    basis.append(f"心率较短期基线高约 {hr_delta:.0f} bpm")
                if isinstance(valence, (int, float)) and valence <= -0.25:
                    score += 1
                    basis.append("研究效价代理连续偏低")
                if isinstance(attention, (int, float)) and attention <= 35:
                    score += 0.5
                    basis.append("注意力代理出现明显波动")
                self.evidence.append({"at": now, "score": score, "basis": basis})
                self.last_evidence_id = evidence_id

            recent = [e for e in self.evidence if now - e["at"] <= 90]
            elevated = [e for e in recent if e["score"] >= 2]
            if len(elevated) >= 3:
                basis = []
                for event in elevated[-3:]:
                    for item in event["basis"]:
                        if item not in basis:
                            basis.append(item)
                return self._base(
                    "notice",
                    "连续波动，建议主动确认感受",
                    "最近几次有效数据同时出现了生理唤醒和研究分数波动。它不能说明你正在焦虑或失控，但值得暂停一下并自我确认。",
                    "我注意到最近几次数据比你的短期基线波动更大。它不代表诊断。你可以先停一下，确认自己现在是否紧绷。",
                    ["用 0–10 分给当前紧绷感打分", "离开屏幕并缓慢呼吸 1 分钟", "如果主观感受也很难受，告诉我或联系可信任的人"],
                    basis,
                )

            valid_sources = []
            if state.get("eeg", {}).get("valid"):
                valid_sources.append("EEG")
            if heart.get("valid"):
                valid_sources.append("心率")
            if not valid_sources:
                return self._base(
                    "collecting",
                    "等待可信的实时数据",
                    "设备尚未形成连续有效窗口。系统不会用旧数据或假数据推断你的状态。",
                    "设备还在准备中。请确认佩戴和连接状态，我们会等到数据连续后再给提示。",
                    ["检查 EEG 接触质量", "确认手表或 HeartCast 正在广播", "也可以直接告诉我你此刻的感受"],
                    [],
                    "none",
                )

            return self._base(
                "steady",
                "节律平稳，继续按自己的节奏",
                "当前没有观察到需要打断你的持续组合变化。系统仍会保持安静监测。",
                "现在的节律比较平稳。继续按自己的速度来，需要我时随时告诉我。",
                ["保持自然呼吸", "每 45–60 分钟短暂活动", "完成困难任务后记得给自己肯定"],
                ["有效来源：" + "、".join(valid_sources)],
            )
