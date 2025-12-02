


def calculate_mex(arr):
    n = len(arr)
    mex_table = [] 
    for i in range(n):
        seen = set()  # To track elements in the current subarray
        mex = 0  # Start with the smallest non-negative integer
        for j in range(i, n):
            seen.add(arr[j])
            while mex in seen:
                mex += 1
            mex_table.append((i, j, mex))  # Add the MEX of the subarray (i, j)
    return mex_table

# Test case
arr = [3]
print(calculate_mex(arr))
