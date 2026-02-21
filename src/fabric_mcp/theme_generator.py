# Theme Generator
# Generates dynamic Power BI themes based on input colors.

import json
from pydantic import BaseModel, Field

class ThemeConfig(BaseModel):
    name: str = "custom"
    dataColors: list[str] = Field(default_factory=lambda: ["#01B8AA", "#374649", "#FD625E", "#F2C80F"])
    background: str = "#FFFFFF"
    foreground: str = "#252423"

def generate_theme(config: ThemeConfig) -> str:
    """Generate a Power BI JSON theme from configuration."""
    theme = {
        "name": config.name,
        "dataColors": config.dataColors,
        "visualStyles": {
            "*": {
                "*": {
                    "background": [{"color": {"solid": {"color": config.background}}}],
                    "title": [{"fontColor": {"solid": {"color": config.foreground}}}],
                    "legend": [{"labelColor": {"solid": {"color": config.foreground}}}]
                }
            }
        }
    }
    return json.dumps(theme, indent=2)

if __name__ == "__main__":
    print(generate_theme(ThemeConfig(name="Dark Mode", background="#121212", foreground="#FFFFFF")))
