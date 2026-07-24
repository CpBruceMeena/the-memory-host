"""Prompt templates for the Memory Game bot dialog.

Replaces LLM dependency with pre-written categorized templates and
random selection. Provides natural variety in bot responses without
the cost, latency, or complexity of an external language model.

Categories:
    start        — Welcome messages when game begins
    round_intro  — Announce round number and word sequence
    success      — User answers correctly (round pass)
    failure      — User answers incorrectly
    game_over    — Final score announcement (won or lost)
    interrupt    — Recovery phrases after user interrupts bot
    waiting      — Gentle prompts when user is slow to respond
"""

from __future__ import annotations

import random
from typing import Optional


class PromptTemplateSelector:
    """Selects random prompt templates for bot dialog.

    Usage:
        selector = PromptTemplateSelector()
        prompt = selector.get("start", player_name="Alice")
        # Returns a random welcome template with {player_name} filled in
    """

    def __init__(self) -> None:
        self.templates: dict[str, list[str]] = {
            # ── Start / Welcome ────────────────────────────────────
            "start": [
                "Welcome to the Memory Host, {player_name}. I'm going to say a "
                "sequence of words. Your job is to repeat them back to me exactly "
                "as I said them. Ready? Let's begin.",
                "Hey there, {player_name}. Welcome to the memory challenge. "
                "Listen carefully to each word I say, and then repeat them back "
                "to me in the same order. Let's see how far you can go.",
                "Hello, {player_name}, and welcome to The Memory Host. "
                "I'll speak a sequence of words. Your task is to remember them "
                "and repeat them back. The sequences get longer each round. "
                "Good luck.",
            ],
            # ── Round Introduction ─────────────────────────────────
            "round_intro": [
                "Round {round_number}. Here are your words. {sequence}. "
                "Now it's your turn to repeat them back to me.",
                "Okay, round {round_number}. Listen closely. {sequence}. "
                "Go ahead and repeat that back.",
                "Here comes round {round_number}. {sequence}. "
                "Take your time and say them back when you're ready.",
                "Round {round_number}. {sequence}. "
                "Repeat those back to me whenever you're ready.",
            ],
            # ── Success / Round Pass ────────────────────────────────
            "success": [
                "That's correct. You've got a great memory. Let's move to round "
                "{round_number}. Your score is now {score}. "
                "Here's your next sequence. {sequence}.",
                "Perfect. You nailed it. On to round {round_number}. "
                "Score: {score}. Listen up. {sequence}.",
                "Absolutely right. You're on fire. Round {round_number} coming up. "
                "Score: {score}. Your words are. {sequence}.",
                "Correct. Excellent memory. Let's see how you do in round "
                "{round_number}. Current score: {score}. "
                "Here's your new sequence. {sequence}.",
            ],
            # ── Failure / Wrong Answer ─────────────────────────────
            "failure": [
                "Oh, that's not quite right. The correct sequence was. "
                "{correct_sequence}. You said. {user_said}. "
                "Your final score is {score}. Thanks for playing The Memory Host.",
                "Almost. The right answer was. {correct_sequence}. "
                "You said. {user_said}. Game over. Final score: {score}. "
                "Great effort.",
                "Sorry, that wasn't correct. I was looking for. {correct_sequence}. "
                "You replied with. {user_said}. "
                "Game over. You scored {score} points. Well played.",
                "Not quite. The sequence was. {correct_sequence}. "
                "You said. {user_said}. Final score: {score}. "
                "Better luck next time.",
            ],
            # ── Game Over / Win ────────────────────────────────────
            "game_over": [
                "That's the game. You've completed all rounds. "
                "Your final score is {score}. You're a memory master. "
                "Congratulations, {player_name}.",
                "Incredible. You made it through all the rounds. "
                "Final score: {score}. That's amazing. Thanks for playing.",
                "You did it. Every round completed with a perfect score of {score}. "
                "You are the ultimate Memory Host champion, {player_name}.",
            ],
            # ── Interruption Recovery ──────────────────────────────
            "interrupt": [
                "Oh, you cut me off! Go ahead, I'm listening.",
                "Sorry, go ahead! What were you going to say?",
                "You jumped in! That's fine, take the floor.",
                "I'll let you speak first. Go ahead!",
            ],
            # ── Waiting / No Response ──────────────────────────────
            "waiting": [
                "Take your time, I'm listening...",
                "No rush, just repeat the words when you're ready.",
                "I'm still here, waiting for your response.",
                "Whenever you're ready, just say the words back to me.",
            ],
        }

    def get(
        self,
        category: str,
        default: Optional[str] = None,
        **kwargs: str | int,
    ) -> str:
        """Get a random template from the specified category.

        Args:
            category: Template category key (e.g. 'start', 'success').
            default: Fallback text if the category is not found.
            **kwargs: Format variables to fill into the template.

        Returns:
            A randomly selected, formatted template string.
        """
        templates = self.templates.get(category)
        if not templates:
            return default or ""

        template = random.choice(templates)
        return template.format(**kwargs)

    def add_template(self, category: str, template: str) -> None:
        """Add a new template to an existing or new category.

        Args:
            category: Template category key.
            template: The template string with {placeholder}s.
        """
        if category not in self.templates:
            self.templates[category] = []
        self.templates[category].append(template)

    def list_categories(self) -> list[str]:
        """Get all available template category names."""
        return list(self.templates.keys())

    def count_templates(self, category: Optional[str] = None) -> int:
        """Count templates, optionally filtered by category.

        Args:
            category: If provided, count only this category.
                     Otherwise, count all templates across all categories.
        """
        if category:
            return len(self.templates.get(category, []))
        return sum(len(templates) for templates in self.templates.values())
