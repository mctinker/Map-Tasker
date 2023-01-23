

from tkinter import *
from tkinter import messagebox
from tkinter import colorchooser
from tkinter import filedialog
from tkinter import simpledialog

class App(Tk):
  def __init__(self):
    Tk.__init__(self)

    self.geometry("400x400")

    self.title("MapTasker")
    # self.pack(padx=5, pady=5)

    self.resizable(True, True)
    self.btnInfo = Button(self, text = "info", command = self.showInfo)
    self.btnInfo.grid()

    self.btnQuestion = Button(self, text = "question", command = self.showQuestion)
    self.btnQuestion.grid()

    self.btnName = Button(self, text = "string input", command = self.askName)
    self.btnName.grid()

    self.btnInt = Button(self, text = "int input", command = self.askNumber)
    self.btnInt.grid()

    self.btnColor = Button(self, text = "color", command = self.showColor)
    self.btnColor.grid()

    self.btnFile = Button(self, text = "file", command = self.showFile)
    self.btnFile.grid()

    self.mainloop()

  def showInfo(self):
    messagebox.showinfo(title = "Hi there", message = "This is info")

  def showQuestion(self):
    response = messagebox.askquestion(title = "One question:", message = "Are you crazy?")
    print(response)
    if response == "yes":
      messagebox.showinfo(message = "but it's a good kind of crazy")
    else:
      messagebox.showinfo(message = "are you sure?")

  def askName(self):
    name = simpledialog.askstring("", "what is your name?")
    messagebox.showinfo(message = "Hi there, {}".format(name))

  def askNumber(self):
    number = simpledialog.askinteger("", "What's your favorite number")
    messagebox.showinfo(message = "I like {} too".format(number))

  def showColor(self):
    myColor = colorchooser.askcolor()
    print(myColor)
    self["bg"] = myColor[1]

  def showFile(self):
    myFile = filedialog.askopenfile()
    for line in myFile:
      print(line.rstrip())

    myFile.close()

def main():
  app = App()

if __name__ == "__main__":
  main()