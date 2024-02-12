# coding=utf-8
# Copyright 2020 The HuggingFace Team Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a clone of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time
import unittest

from transformers import AutoTokenizer, is_torch_available
from transformers.testing_utils import require_torch, torch_device

from ..test_modeling_common import ids_tensor


if is_torch_available():
    import torch

    from transformers.generation import (
        MaxLengthCriteria,
        MaxNewTokensCriteria,
        MaxTimeCriteria,
        StoppingCriteriaList,
        StopStringCriteria,
        validate_stopping_criteria,
    )


@require_torch
class StoppingCriteriaTestCase(unittest.TestCase):
    def _get_tensors(self, length):
        batch_size = 3
        vocab_size = 250

        input_ids = ids_tensor((batch_size, length), vocab_size)
        scores = torch.ones((batch_size, length), device=torch_device, dtype=torch.float) / length
        return input_ids, scores

    def test_list_criteria(self):
        input_ids, scores = self._get_tensors(5)

        criteria = StoppingCriteriaList(
            [
                MaxLengthCriteria(max_length=10),
                MaxTimeCriteria(max_time=0.1),
            ]
        )

        self.assertFalse(all(criteria(input_ids, scores)))

        input_ids, scores = self._get_tensors(9)
        self.assertFalse(all(criteria(input_ids, scores)))

        input_ids, scores = self._get_tensors(10)
        self.assertTrue(all(criteria(input_ids, scores)))

    def test_max_length_criteria(self):
        criteria = MaxLengthCriteria(max_length=10)

        input_ids, scores = self._get_tensors(5)
        self.assertFalse(all(criteria(input_ids, scores)))

        input_ids, scores = self._get_tensors(9)
        self.assertFalse(all(criteria(input_ids, scores)))

        input_ids, scores = self._get_tensors(10)
        self.assertTrue(all(criteria(input_ids, scores)))

    def test_max_new_tokens_criteria(self):
        criteria = MaxNewTokensCriteria(start_length=5, max_new_tokens=5)

        input_ids, scores = self._get_tensors(5)
        self.assertFalse(all(criteria(input_ids, scores)))

        input_ids, scores = self._get_tensors(9)
        self.assertFalse(all(criteria(input_ids, scores)))

        input_ids, scores = self._get_tensors(10)
        self.assertTrue(all(criteria(input_ids, scores)))

        criteria_list = StoppingCriteriaList([criteria])
        self.assertEqual(criteria_list.max_length, 10)

    def test_max_time_criteria(self):
        input_ids, scores = self._get_tensors(5)

        criteria = MaxTimeCriteria(max_time=0.1)
        self.assertFalse(all(criteria(input_ids, scores)))

        criteria = MaxTimeCriteria(max_time=0.1, initial_timestamp=time.time() - 0.2)
        self.assertTrue(all(criteria(input_ids, scores)))

    def test_validate_stopping_criteria(self):
        validate_stopping_criteria(StoppingCriteriaList([MaxLengthCriteria(10)]), 10)

        with self.assertWarns(UserWarning):
            validate_stopping_criteria(StoppingCriteriaList([MaxLengthCriteria(10)]), 11)

        stopping_criteria = validate_stopping_criteria(StoppingCriteriaList(), 11)

        self.assertEqual(len(stopping_criteria), 1)

    def test_stop_string_criteria(self):
        true_strings = [
            "<|im_start|><|im_end|>",
            "<|im_start|><|im_end|<|im_end|>",
            ">><|im_start|>>stop",
            "stop"
        ]
        false_strings = [
            "<|im_start|><|im_end|",
            "<|im_start|><|im_end|<|im_end|",
            "<|im_end|><|im_start|>",
            "<|im_end|<>stop<|im_end|",
        ]
        too_short_strings = ["<|im_end|", "|im_end|>", "s", "end"]

        # Use a tokenizer that won't actually have special tokens for these
        tokenizer = AutoTokenizer.from_pretrained("openai-community/gpt2")
        tokenizer.pad_token_id = tokenizer.eos_token_id
        tokenizer.padding_side = "left"
        true_input_ids = tokenizer(true_strings, return_tensors="pt", padding="longest", add_special_tokens=False)
        false_input_ids = tokenizer(false_strings, return_tensors="pt", padding="longest", add_special_tokens=False)
        too_short_input_ids = tokenizer(
            too_short_strings, return_tensors="pt", padding="longest", add_special_tokens=False
        )
        scores = None
        criteria = StopStringCriteria(tokenizer=tokenizer, stop_strings=["<|im_end|>", "stop"])
        for i in range(len(true_strings)):
            self.assertTrue(criteria(true_input_ids["input_ids"][i : i + 1], scores))
        for i in range(len(false_strings)):
            self.assertFalse(criteria(false_input_ids["input_ids"][i : i + 1], scores))
        for i in range(len(too_short_strings)):
            self.assertFalse(criteria(too_short_input_ids["input_ids"][i : i + 1], scores))

        # Now try it with a tokenizer where those are actually special tokens
        tokenizer = AutoTokenizer.from_pretrained("cognitivecomputations/dolphin-2.5-mixtral-8x7b")
        tokenizer.padding_side = "left"
        true_input_ids = tokenizer(true_strings, return_tensors="pt", padding="longest", add_special_tokens=False)
        false_input_ids = tokenizer(false_strings, return_tensors="pt", padding="longest", add_special_tokens=False)
        too_short_input_ids = tokenizer(
            too_short_strings, return_tensors="pt", padding="longest", add_special_tokens=False
        )
        criteria = StopStringCriteria(tokenizer=tokenizer, stop_strings=["<|im_end|>", "stop"])
        for i in range(len(true_strings)):
            self.assertTrue(criteria(true_input_ids["input_ids"][i : i + 1], scores))
        for i in range(len(false_strings)):
            self.assertFalse(criteria(false_input_ids["input_ids"][i : i + 1], scores))
        for i in range(len(too_short_strings)):
            self.assertFalse(criteria(too_short_input_ids["input_ids"][i : i + 1], scores))
