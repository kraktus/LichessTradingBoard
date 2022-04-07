# LichessTradingBoard
Create candlestick graph from lichess rating history of a user

![example](/german11_blitz_fixed.png)

## Installation

After cloning the repository, create a `venv`
```
python3 -m venv venv
```
And turn it on
```
source venv/bin/activate
```
Install the dependencies
```
pip3 install -r requirements.txt
```

## Use

It comes as a CLI. To remove display logging, use `python3 -O`
Ex:
```
python3 -O LichessTradingBoard german11 blitz 4000 True
```
