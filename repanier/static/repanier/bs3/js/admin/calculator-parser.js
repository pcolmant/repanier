// # calculator-parser.js from https://jorendorff.github.io/calc/docs/calculator-parser.html
//
// A simple calculator language
// This program parses a very simple language that just does a little basic
// arithmetic. Here are some simple examples of the sort of thing you can
// write in the calculator language:
//
//   * `2 + 2`
//   * `1 * 2 + 3 * 4 + 5 / 6`
//   * `3 + 1/(7 + 1/(15 + 1/(1 + 1/(292 + 1/(1 + 1/(1 + 1/1))))))`
//   * `1 / ((z + 1) * (z - 1))`
//

// ## Part One – Breaking code down into tokens

// This function, `tokenize(code)`, takes a string `code` and splits it into
// *tokens*, the numbers, words, and symbols that make up our little calculator
// mini-language.
function tokenize(code) {
    var results = [];
    var tokenRegExp = /\s*([A-Za-z]+|[0-9.]+|\S)\s*/g;

    var m;
    while ((m = tokenRegExp.exec(code)) !== null)
        results.push(m[1]);
    return results;
}
// Here are a few helper functions for working with tokens. To keep things
// simple, a number is any sequence of digits.
function isNumber(token) {
    return token !== undefined && token.match(/^[0-9.]+$/) !== null;
}
// And a *name*, or identifier, is any sequence of letters.
function isName(token) {
    return token !== undefined && token.match(/^[A-Za-z]+$/) !== null;
}
// ## Part Two – The parser
// The parser’s job is to decode the input and build a collection of objects
// that represent the code.
//
// (This is just like the way a Web browser decodes an HTML file and builds the
// DOM. The part that does that is called the HTML parser.)
// Parse the given string `code` as an expression in our little language.
//
function parse(code) {
    // Break the input into tokens.
    var tokens = tokenize(code);
    // The parser will do a single left-to-right pass over `tokens`, with no
    // backtracking. `position` is the index of the next token. Start at
    // 0. We’ll increment this as we go.
    var position = 0;
    // `peek()` returns the next token without advancing `position`.
    function peek() {
        return tokens[position];
    }
    // `consume(token)` consumes one token, moving `position` to point to the next one.
    function consume(token) {
        position++;
    }
    // Now we have the functions that are actually responsible for parsing.
    // This is the cool part. Each group of syntax rules is translated to one
    // function.
    // Parse a *PrimaryExpr*—that is, tokens matching one of the three syntax
    // rules below. Whatever kind of expression we find, we return the corresponding
    // JS object.
    function parsePrimaryExpr() {
        var t = peek();

        if (isNumber(t)) {
            consume(t);
            return {type: "number", value: t};
        } else if (isName(t)) {
            consume(t);
            return {type: "name", id: t};
        } else if (t === "(") {
            consume(t);
            var expr = parseExpr();
            if (peek() !== ")")
                throw new SyntaxError("expected )");
            consume(")");
            return expr;
        } else {
            // If we get here, the next token doesn’t match any of the three
            // rules. So it’s an error.
            throw new SyntaxError("expected a number, a variable, or parentheses");
        }
    }

    function parseMulExpr() {
        var expr = parsePrimaryExpr();
        var t = peek();
        while (t === "*" || t === "/") {
            consume(t);
            var rhs = parsePrimaryExpr();
            expr = {type: t, left: expr, right: rhs};
            t = peek();
        }
        return expr;
    }

    function parseExpr() {
        var expr = parseMulExpr();
        var t = peek();
        while (t === "+" || t === "-") {
            consume(t);
            var rhs = parseMulExpr();
            expr = {type: t, left: expr, right: rhs};
            t = peek();
        }
        return expr;
    }

    // Now all that remains, really, is to call `parseExpr()` to parse an *Expr*.
    var result = parseExpr();
    // Well, one more thing. Make sure `parseExpr()` consumed *all* the
    // input. If it didn’t, that means the next token didn’t match any syntax
    // rule, which is an error.
    if (position !== tokens.length)
        throw new SyntaxError("unexpected '" + peek() + "'");

    return result;
}
// ## Part Three – The evaluation
function evaluateAsFloat(code) {
    // If code end with "="
    if(code.slice(-1) === "=") {
        // Take the content of code but last character which is "="
        // and replace all , with .
        code = code.slice(0, -1).replaceAll(",",".");
        function evaluate(obj) {
            switch (obj.type) {
                case "number":
                    return parseFloat(obj.value);
                case "+":
                    return evaluate(obj.left) + evaluate(obj.right);
                case "-":
                    return evaluate(obj.left) - evaluate(obj.right);
                case "*":
                    return evaluate(obj.left) * evaluate(obj.right);
                case "/":
                    return evaluate(obj.left) / evaluate(obj.right);
            }
        }

        return evaluate(parse(code)).toFixed(2).toString().replaceAll(".",",");
    } else {
        return code
    }
}