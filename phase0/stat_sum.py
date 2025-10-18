# find std_dev,var,mean,median from given file

filename = "numbers.txt"

try:
    with open(filename,'r') as file:
        content = file.read().split()
        numbers = [float(num) for num in content if num.strip()]

    if not numbers:
        print("the file is empty")
    else:
        mean = sum(numbers)/len(numbers)

        numbers.sort()
        n = len(numbers)
        if n%2 != 0:
            median = numbers[n//2]
        else:
            median = (numbers[n//2-1]+numbers[n//2])/2

        variance = sum((x-mean)**2 for x in numbers)/(n-1)
        std_dev = variance**0.5

        print(f"Numbers:{numbers}")
        print(f"Mean: {mean:.2f}")
        print(f"median: {median:.2f}")
        print(f"variance:{variance:.2f}")
        print(f"standard deviation: {std_dev:.2f}")

except FileNotFoundError:
    print(f"File '{filename}' not found")

except ValueError:
    print(f"the file contains non numeric data")

except Exception as e:
    print("an unexpected error occur",e)