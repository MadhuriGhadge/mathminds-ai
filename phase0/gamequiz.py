questions = [
    {
        "question":"what is the capital of india ?",
        "options" : ["A. Paris","B. Berlin","C. Delhi","D. Rome"],
        "answer"  : "C"
    },
    {
        "question":"which is the best language for programming ?",
        "options" : ["A. Python","B. GO","C. C++","D. Ruby"],
        "answer"  : "A"
    },
    {
        "question":"which is the best climate city?",
        "options" : ["A. Nagpur","B. Mumbai","C. Chennai","D. Nashik"],
        "answer"  : "D"
    },
     {
        "question":"who is the founder of spaceX ?",
        "options" : ["A. Elon Musk","B. Mark zuckerberg","C. Sundar Pichai","D. Steve Jobs"],
        "answer"  : "A"
    },
     {
        "question":"which city is known as orange city ?",
        "options" : ["A. Nagpur","B. Mumbai","C. Chennai","D. Nashik"],
        "answer"  : "A"
    }
]


def ask_questions(question):
    print("\n"+ question["question"])
    for option in question["options"]:
        print(option)
    user_answer = input("your answer (A/B/C/D): ").upper()
    return user_answer

def quiz_game():
    print("welcome to the quiz game!")
    score = 0
    user_answers = []
    for q in questions:
        user_answer = ask_questions(q)
        user_answers.append(user_answer)
        if user_answer == q["answer"]:
            score += 1
    print(f"\n your final score is {score}/{len(questions)}")

    print(f"Review of your answers !\n")
    for i,q in enumerate(questions):
        print(f"Q{i+1} : {q['question']}")
        print(f"your answer :{user_answers[i]} " + f"correct answer : {q['answer']}")

    


quiz_game()