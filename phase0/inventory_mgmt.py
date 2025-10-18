inventory = [
    {"name":"laptop","price":55000,"quantity":10},
    {"name":"Mouse","price":500,"quantity":50},
    {"name":"keyboard","price":1500,"quantity":30}
]
print("welcome to the inventory :: ")
while True:
    print("\n1.view inventory - don't touch anything")
    print("2.add product")
    print("3.update product")
    print("4.Remove product")
    print("5.Total inventory value - only if you can buy it otherwise don't ask")
    print("6.get out of here(aasan bhasha mein bahar jaiye)\n")

    choice = int(input("enter the choice of yours"))

    if choice == 1:
        for item in inventory:
            print(f"{item['name']} - item['price'] ({item['quantity']}pcs)")
    elif choice == 2:
        name = input("enter product name:")
        price = float(input("enter product name:"))
        quantity = int(input("enter product quantity:"))
        new_product = {"name": name, "price": price, "quantity": quantity}
        for item in inventory:
            if item["name"].lower() == name.lower():
                print("Product already exists! Try updating it instead.")
                break
            else:
                inventory.append(new_product)
                print(f"{name} added successfully!")
    elif choice == 3:
        name = input("enter the name of the product you want to update")
        for item in inventory:
            if item["name"].lower() == name.lower():
                new_price = float(input(f"Enter new price for {name}: "))
                new_qty = int(input(f"Enter new quantity for {name}: "))
                item["price"] = new_price
                item["quantity"] = new_qty
                print(f"{name} updated successfully!")
                break
        else:
            print(f"{name} not found in inventory.")

    elif choice == 4:
        name = input("Enter the name of the product you want to remove: ")
        for item in inventory:
            if item["name"].lower() == name.lower():
                inventory.remove(item)
                print(f"{name} removed from inventory!")
                break
        else:
            print(f"{name} not found in inventory.")

    elif choice == 5:
        total_value = sum(item["price"] * item["quantity"] for item in inventory)
        print(f"Total inventory value: {total_value}")

    elif choice == 6:
        print("Exiting... Thank you for visiting the inventory")
        break

    else:
        print("Invalid choice! Try again.")