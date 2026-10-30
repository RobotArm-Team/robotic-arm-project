"""手势置信度时序平滑：对各类别的模型置信度做指数滑动平均（EMA）。

目的：单帧识别常有抖动（同一手势在相邻帧的 label/score 小幅跳变），
直接采信会让下发命令闪烁。跨帧平滑后：
- 持续稳定的手势其平滑置信度会收敛到高位（更可信、更接近真实水平）；
- 偶尔的误帧会被“拉低”而不足以触发下发。

这是 MediaPipe 官方推荐的去抖手段，不改变任何识别语义，只让输出更稳。
"""

from __future__ import annotations


class GestureSmoother:
    def __init__(self, alpha: float = 0.6, decay: float = 0.6) -> None:
        """
        alpha: 当前帧对平滑值的权重（越大越跟手，越小越平滑）。
        decay: 非当前帧类别的衰减系数（<1，使旧类别随时间淡出）。
        """
        self.alpha = alpha
        self.decay = decay
        self._ema: dict = {}

    def update(self, top_cat: str, top_score: float):
        """喂入当前帧的(类别, 置信度)，返回(平滑后最佳类别, 其平滑置信度)。"""
        prev = self._ema.get(top_cat, top_score)
        self._ema[top_cat] = self.alpha * top_score + (1 - self.alpha) * prev
        for k in list(self._ema):
            if k != top_cat:
                self._ema[k] *= self.decay
        best = max(self._ema, key=self._ema.get)
        return best, self._ema[best]

    def reset(self) -> None:
        """无手/重新检测时清空，避免旧状态残留。"""
        self._ema = {}
