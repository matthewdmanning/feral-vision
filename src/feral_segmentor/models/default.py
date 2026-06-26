"""Default no-config model for sanity checks and tests."""

from __future__ import annotations

import torch.nn.functional as F
from torch import nn

from feral_segmentor.models.registry import register


@register("net")
class Net(nn.Module):
    """Classic PyTorch tutorial CNN; the default architecture."""

    def __init__(self) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(3, 6, 5)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.fc1 = nn.Linear(16 * 5 * 5, 120)
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, 10)

    def forward(self, x):
        """Run the forward pass; expects (N, 3, 32, 32) input."""
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(-1, 16 * 5 * 5)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)

    @classmethod
    def from_config(cls, cfg) -> "Net":
        """Construct Net; ignores cfg (no architecture hyperparameters)."""
        return cls()
