"""Cellular Automata module."""

from functools import partial

from flax import nnx
import jax
import jax.numpy as jnp

from cax.core.perceive.perceive import Perceive
from cax.core.update.update import Update
from cax.types import Input, State
from cax.nn.vae import Encoder


class CA(nnx.Module):
    """Cellular Automata class."""

    perceive: Perceive
    update: Update

    def __init__(self, perceive: Perceive, update: Update):
        """Initialize the CA.

        Args:
                perceive: Perception module.
                update: Update module.

        """
        self.perceive = perceive
        self.update = update
    
    @nnx.jit
    def step(self, state: State, input: Input | None = None) -> State:
        """Perform a single step of the CA.

        Args:
                state: Current state.
                input: Optional input.

        Returns:
                Updated state.

        """
        perception = self.perceive(state)
        state = self.update(state, perception, input)
        return state

    @partial(nnx.jit, static_argnames=("num_steps", "all_steps", "input_in_axis"))
    def __call__(
        self,
        first_state: State,
        input: Input | None = None,
        *,
        num_steps: int = 1,
        all_steps: bool = False,
        input_in_axis: int | None = None,
    ) -> State:
        """Run the CA for multiple steps.

        Args:
                state: Initial state.
                input: Optional input.
                num_steps: Number of steps to run.
                all_steps: Whether to return all intermediate states.
                input_in_axis: Axis for input if provided for each step.

        Returns:
                Final state or all intermediate states if all_steps is True.

        """

        def step(
            carry: tuple[CA, State], input: Input | None
        ) -> tuple[tuple[CA, State], State]:
            ca, state = carry
            state = ca.step(state, input)
            return (ca, state), state if all_steps else None  # type: ignore

        (_, last_state), states = nnx.scan(
            step,
            in_axes=(nnx.Carry, input_in_axis),
            length=num_steps,
        )((self, first_state), input)

        return (
            jnp.concatenate([first_state[None, ...], states], axis=0)
            if all_steps
            else last_state
        )


class UnsupervisedCA(CA):
    encoder: Encoder

    def __init__(self, perceive, update, encoder):
        super().__init__(perceive, update)

        self.encoder = encoder

    def encode(self, target, key):
        mean, logvar = self.encoder(target)
        target_enc = mean + jax.random.normal(key, mean.shape) * jnp.exp(0.5 * logvar)
        return target_enc
