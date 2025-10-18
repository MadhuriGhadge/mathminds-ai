user_account = {
    "name":"madhuri ghadge",
    "pin":2004,
    "balance":780
}

print("--------------welcome to Madhuri's ATM-----------------")

enter_pin = int(input("Enter you 4 digit pin:"))
if enter_pin == user_account["pin"]:
    print(f"welcome,{user_account['name']}!,your account balance is only {user_account['balance']}ruppes,so use your brain to make money")
else:
    print(f"you forgot your ATM pin again...........ahh....silly girl")
    exit()


### now I use my brain and made some money so let's add it to account
    
while True:
    print("\nselect an option")
    print("1.Check Balance")
    print("2.deposit money")
    print("3.withdraw money")
    print("4.Exit")

    choice = int(input("enter your choice:"))

    if choice == 1:
        print(f"your balance is only {user_account['balance']} poor madhuri,get rich soon")
    elif choice == 2:
        amount = float(input("enter the little money you have:"))
        user_account['balance'] += amount
        print(f"{amount} deposited successfully, and that's still less! earn more sweetheart")
    elif choice == 3:
        amount = float(input("how much money you need for shopping now:"))
        if amount <= user_account['balance']:
            user_account['balance'] -= amount
            print(f"{amount} withdrawn, you are spending too much nowadays")
        else:
            print("I don't have any money for you,earn by yourself")
    elif choice == 4:
        print("thank you for asking money which you can't earn")
        break
    else:
        print("inavlid option try again")

print("Session ended. Madhuris ATM is now broke. ")