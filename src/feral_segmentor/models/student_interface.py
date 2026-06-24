import torch.nn as nn


class StudentModelInterface(nn.Module):
    """
    Wrapper expectation for user-supplied student model.
    No architecture defined here.
    """

    def __init__(self, model: nn.Module):
        super().__init__()
        self.model = model

    def forward(self, x):
        return self.model(x)
