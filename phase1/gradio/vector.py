import gradio as gr 
class Vector:
    def __init__(self, values):
        self.values = values

    def __repr__(self):
        return f"Vector({self.values})"
    
    def add(self,other):
        if len(self.values) != len(other.values):
            raise ValueError("Vectors must be of same length")
        return Vector([a+b for a,b in zip(self.values, other.values)])
    

    def scalar_multiply(self,scalar):
        return Vector([scalar * x for x in self.values])
    

    def dot(self,other):
        if len(self.values) != len(other.values):
            raise ValueError("vectors must be same length")
        return sum(a*b for a,b in zip(self.values,other.values))
    

class Matrix:
    def __init__(self,values):
        self.values = values

    def __repr__(self):
        return f"Matrix({self.values})"
    
    def multiply(self,other):
        A = self.values 
        B = other.values  

        if len(A[0]) != len(B):
            raise ValueError("column count of A must equal row count of B")
        

        result = [] 
        for i in range(len(A)):
            row = [] 
            for j in range(len(B[0])):
                s = 0
                for k in range(len(B)):
                    s += A[i][k] * B[k][j]
                row.append(s)
            result.append(row)

        return Matrix(result)


def multiply_matrices(mat1, mat2):
    M1 = Matrix(eval(mat1))
    M2 = Matrix(eval(mat2))
    result = M1.multiply(M2)
    return result.values

demo = gr.Interface(
    fn = multiply_matrices,
    inputs = [
        gr.Textbox(label="Matrix 1 (e.g. [[1,2],[3,4]])"),
        gr.Textbox(label="Matrix 2 (e.g. [[5,6],[7,8]])")
    ],
    outputs = "text",
    title = "Matrix Multiplication App"
)

demo.launch()