"""Instruction version of HumanEval used for WizardCoder Models evaluation
Evaluating Large Language Models Trained on Code
https://arxiv.org/abs/2107.03374

The HumanEval dataset released by OpenAI includes 164 programming problems with a function signature,
docstring, body, and several unit tests. 
They were handwritten to ensure not to be included in the training set of code generation models.

Homepage: https://github.com/openai/human-eval
"""

import re

from evaluate import load

from lm_eval.base import Task

_CITATION = """
@misc{chen2021evaluating,
      title={Evaluating Large Language Models Trained on Code},
      author={Mark Chen and Jerry Tworek and Heewoo Jun and Qiming Yuan and Henrique Ponde de Oliveira Pinto and Jared Kaplan and Harri Edwards and Yuri Burda and Nicholas Joseph and Greg Brockman and Alex Ray and Raul Puri and Gretchen Krueger and Michael Petrov and Heidy Khlaaf and Girish Sastry and Pamela Mishkin and Brooke Chan and Scott Gray and Nick Ryder and Mikhail Pavlov and Alethea Power and Lukasz Kaiser and Mohammad Bavarian and Clemens Winter and Philippe Tillet and Felipe Petroski Such and Dave Cummings and Matthias Plappert and Fotios Chantzis and Elizabeth Barnes and Ariel Herbert-Voss and William Hebgen Guss and Alex Nichol and Alex Paino and Nikolas Tezak and Jie Tang and Igor Babuschkin and Suchir Balaji and Shantanu Jain and William Saunders and Christopher Hesse and Andrew N. Carr and Jan Leike and Josh Achiam and Vedant Misra and Evan Morikawa and Alec Radford and Matthew Knight and Miles Brundage and Mira Murati and Katie Mayer and Peter Welinder and Bob McGrew and Dario Amodei and Sam McCandlish and Ilya Sutskever and Wojciech Zaremba},
      year={2021},
      eprint={2107.03374},
      archivePrefix={arXiv},
      primaryClass={cs.LG}
}
"""


def generate_prompt(input, function_signature):
    INSTRUCTION = f"""Below is an instruction that describes a task. Write a response that appropriately completes the request.


### Instruction:
Create a Python script for {function_signature} problem:
{input}

### Response:"""
    return INSTRUCTION

def create_all_tasks():
    """Creates a dictionary of tasks from a list of levels
    :return: {task_name: task}
        e.g. {multiple-py: Task, multiple-java: Task}
    """
    return {"wizardcoder-repo-codegen-long-context": create_task(False, False), "wizardcoder-repo-codegen-short-context-doc": create_task(True, True),
             "wizardcoder-repo-codegen-short-context-nodoc": create_task(True, False) }

def create_task(short_context, contained_doc):
    class RepoCodeGen(RepoCodeGenWizardCoder):
        def __init__(self):
            super().__init__(short_context, contained_doc)

    return RepoCodeGen

class RepoCodeGenWizardCoder(Task):
    """A task represents an entire benchmark including its dataset, problems,
    answers, generation settings and evaluation methods.
    """

    DATASET_PATH = "NamCyan/repo-codegen-v3"

    def __init__(self, short_context, contained_doc):

        super().__init__(
            stop_words=[],
            requires_execution=True,
        )

        if short_context:
            self.data_split = "short_context"
        else:
            self.data_split = "long_context"

        if contained_doc:
            self.data_split += "_doc"
        else:
            self.data_split += "_nodoc"

    def get_dataset(self):
        """Returns dataset for the task or an iterable of any object, that get_prompt can handle"""
        return self.dataset[self.data_split]

    def get_prompt(self, doc):
        """Builds the prompt for the LM to generate from."""
        prompt = doc["prompt"].replace("    ", "\t")
        prompt = generate_prompt(prompt, doc["function_signature"])
        return prompt

    def get_reference(self, doc):
        """Builds the reference solution for the doc (sample from the test dataset)."""
        test_func = doc["check"]
        return "\n" + test_func

    @staticmethod
    def clean_comp(completion):
        # adapted from https://github.com/nlpxucan/WizardLM/blob/main/WizardCoder/src/process_humaneval.py
        if "```python" in completion:
            def_line = completion.index("```python")
            completion = completion[def_line:].strip()
            completion = completion.replace("```python", "")
            try:
                if "```" in completion:
                    next_line = completion.index("```")
                    completion = completion[:next_line].strip()
            except:
                pass
        if '__name__ == "__main__"' in completion:
            next_line = completion.index('if __name__ == "__main__":')
            completion = completion[:next_line].strip()

        if "# Example usage" in completion:
            next_line = completion.index("# Example usage")
            completion = completion[:next_line].strip()
        if completion.startswith("Here's"):
            completion = completion.split("\n")[1:]
            completion = "\n".join(completion)
        result = completion
        return result

    def postprocess_generation(self, generation, idx):
        """Defines the postprocessing for a LM generation.
        :param generation: str
            code generation from LM
        :param idx: int
            index of doc in the dataset to which the generation belongs
            (not used for Humaneval-Task)
        """
        generation = generation.split("### Response:")[-1]
        generation = generation.replace("\t", "    ")
        generation = generation.split("</s>")[0]
        generation = self.clean_comp(generation)
        return generation

    def process_results(self, generations, references):
        """Takes the list of LM generations and evaluates them against ground truth references,
        returning the metric for the generations.
        :param generations: list(list(str))
            list of lists containing generations
        :param references: list(str)
            list of str containing refrences
        """
        code_metric = load("code_eval")
        results, _ = code_metric.compute(
            references=references,
            predictions=generations,
        )
        return results
